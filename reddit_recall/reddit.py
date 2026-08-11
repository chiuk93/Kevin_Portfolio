"""Reddit API client (script-app OAuth, password grant).

Pulls the four history surfaces the API exposes for your own account:
saved, upvoted, submitted, and comments. Reddit does not expose raw
browsing history via the API, so save/upvote anything you want captured.

Note: accounts with 2FA enabled must pass the password as "password:123456"
(current TOTP code appended) — or use an app password if available.
"""

import time

import requests

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
API_BASE = "https://oauth.reddit.com"

# Listing endpoints relative to /user/{username}
SOURCES = ("saved", "upvoted", "submitted", "comments")


class RedditClient:
    def __init__(self, client_id: str, client_secret: str, username: str,
                 password: str, user_agent: str, max_pages: int = 4) -> None:
        self.username = username
        self.user_agent = user_agent
        self.max_pages = max_pages
        self._session = requests.Session()
        self._session.headers["User-Agent"] = user_agent
        self._authenticate(client_id, client_secret, username, password)

    def _authenticate(self, client_id: str, client_secret: str,
                      username: str, password: str) -> None:
        resp = self._session.post(
            TOKEN_URL,
            auth=(client_id, client_secret),
            data={"grant_type": "password", "username": username, "password": password},
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        if "access_token" not in payload:
            raise RuntimeError(f"Reddit auth failed: {payload}")
        self._session.headers["Authorization"] = f"Bearer {payload['access_token']}"

    def _listing(self, source: str):
        """Yield raw (kind, data) children from a paginated user listing."""
        after = None
        for _ in range(self.max_pages):
            params = {"limit": 100}
            if after:
                params["after"] = after
            resp = self._session.get(
                f"{API_BASE}/user/{self.username}/{source}", params=params, timeout=30
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            for child in data.get("children", []):
                yield child.get("kind"), child.get("data", {})
            after = data.get("after")
            if not after:
                break
            time.sleep(1)  # stay well under Reddit's rate limit

    def fetch_history(self) -> list[dict]:
        """Return normalized items across all sources, deduped by fullname."""
        items: dict[str, dict] = {}
        for source in SOURCES:
            for kind, data in self._listing(source):
                item = normalize_item(kind, data, source)
                if item is None:
                    continue
                existing = items.get(item["id"])
                if existing:
                    if source not in existing["sources"]:
                        existing["sources"].append(source)
                else:
                    items[item["id"]] = item
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
        "permalink": f"https://reddit.com{permalink}" if permalink else link,
        "created_utc": data.get("created_utc", 0),
        "sources": [source],
    }
