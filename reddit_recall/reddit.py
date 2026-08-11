"""Reddit API client.

Two modes:

- **Scan mode (default):** reads top posts of the week from configured public
  subreddits (r/ClaudeCode, r/ClaudeAI, ...) plus each post's best comments.
  Uses application-only OAuth — just a client id + secret, no Reddit password.
- **History mode (optional):** additionally reads your own saved / upvoted /
  submitted / commented items. Requires the password grant (username +
  password; 2FA accounts must append ":123456" with the current TOTP code).
"""

import time

import requests

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
API_BASE = "https://oauth.reddit.com"

HISTORY_SOURCES = ("saved", "upvoted", "submitted", "comments")


class RedditClient:
    def __init__(self, client_id: str, client_secret: str, user_agent: str,
                 username: str = "", password: str = "",
                 max_pages: int = 4) -> None:
        self.username = username
        self.max_pages = max_pages
        self._session = requests.Session()
        self._session.headers["User-Agent"] = user_agent
        self._authenticate(client_id, client_secret, username, password)

    def _authenticate(self, client_id: str, client_secret: str,
                      username: str, password: str) -> None:
        if username and password:
            data = {"grant_type": "password", "username": username, "password": password}
        else:
            data = {"grant_type": "client_credentials"}
        resp = self._session.post(
            TOKEN_URL, auth=(client_id, client_secret), data=data, timeout=30
        )
        resp.raise_for_status()
        payload = resp.json()
        if "access_token" not in payload:
            raise RuntimeError(f"Reddit auth failed: {payload}")
        self._session.headers["Authorization"] = f"Bearer {payload['access_token']}"

    def _get(self, path: str, **params) -> dict:
        resp = self._session.get(f"{API_BASE}{path}", params=params, timeout=30)
        resp.raise_for_status()
        time.sleep(1)  # stay well under Reddit's rate limit
        return resp.json()

    # ---------- scan mode ----------

    def fetch_subreddits(self, subreddits: list[str], time_filter: str = "week",
                         post_limit: int = 25, comment_limit: int = 8,
                         min_comment_score: int = 5) -> list[dict]:
        """Top posts of the period from each subreddit, with their best comments."""
        items: dict[str, dict] = {}
        for sub in subreddits:
            listing = self._get(f"/r/{sub}/top", t=time_filter, limit=post_limit)
            for child in listing.get("data", {}).get("children", []):
                data = child.get("data", {})
                item = normalize_item(child.get("kind"), data, f"r/{sub} top-{time_filter}")
                if item is None or item["id"] in items:
                    continue
                comments = self._top_comments(
                    sub, data.get("id", ""), comment_limit, min_comment_score
                )
                if comments:
                    item["body"] += "\n\n--- Top comments ---\n" + "\n\n".join(comments)
                    item["body"] = item["body"][:12000]
                items[item["id"]] = item
        return list(items.values())

    def _top_comments(self, subreddit: str, post_id: str,
                      limit: int, min_score: int) -> list[str]:
        if not post_id:
            return []
        try:
            payload = self._get(
                f"/r/{subreddit}/comments/{post_id}",
                limit=20, depth=1, sort="top",
            )
        except requests.RequestException:
            return []
        comments = []
        if isinstance(payload, list) and len(payload) > 1:
            for child in payload[1].get("data", {}).get("children", []):
                data = child.get("data", {})
                body = (data.get("body") or "").strip()
                if child.get("kind") == "t1" and body and data.get("score", 0) >= min_score:
                    comments.append(f"[+{data['score']}] {body[:1200]}")
                if len(comments) >= limit:
                    break
        return comments

    # ---------- history mode ----------

    def fetch_history(self) -> list[dict]:
        """Normalized items across the user's own listings, deduped by fullname."""
        if not self.username:
            raise RuntimeError("history mode needs REDDIT_USERNAME / REDDIT_PASSWORD")
        items: dict[str, dict] = {}
        for source in HISTORY_SOURCES:
            after = None
            for _ in range(self.max_pages):
                params = {"limit": 100}
                if after:
                    params["after"] = after
                data = self._get(f"/user/{self.username}/{source}", **params).get("data", {})
                for child in data.get("children", []):
                    item = normalize_item(child.get("kind"), child.get("data", {}), source)
                    if item is None:
                        continue
                    existing = items.get(item["id"])
                    if existing:
                        if source not in existing["sources"]:
                            existing["sources"].append(source)
                    else:
                        items[item["id"]] = item
                after = data.get("after")
                if not after:
                    break
        return list(items.values())


def normalize_item(kind: str, data: dict, source: str) -> dict | None:
    """Flatten a Reddit t1 (comment) or t3 (post) into what extraction needs."""
    fullname = data.get("name")
    if not fullname:
        return None
    permalink = data.get("permalink", "")
    if kind == "t3":  # post / link
        title = data.get("title", "(untitled post)")
        body = data.get("selftext", "") or ""
        link = data.get("url", "")
    elif kind == "t1":  # comment
        title = f"Comment in r/{data.get('subreddit', '?')}"
        body = data.get("body", "") or ""
        link = ""
    else:
        return None
    return {
        "id": fullname,
        "kind": kind,
        "title": title,
        "body": body[:8000],  # keep the biggest posts from blowing up the prompt
        "link": link,
        "subreddit": data.get("subreddit", ""),
        "score": data.get("score", 0),
        "permalink": f"https://reddit.com{permalink}" if permalink else link,
        "created_utc": data.get("created_utc", 0),
        "sources": [source],
    }
