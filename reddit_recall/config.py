"""Configuration: environment variables with optional .env file support."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DIGEST_DIR = ROOT / "digests"
BACKLOG_MD = ROOT / "BACKLOG.md"
PROFILE_PATH = ROOT / "context" / "profile.md"


def load_dotenv(path: Path = ROOT / ".env") -> None:
    """Tiny .env loader — KEY=VALUE lines, never overrides real env vars."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


class Config:
    def __init__(self) -> None:
        load_dotenv()
        self.reddit_client_id = os.environ.get("REDDIT_CLIENT_ID", "")
        self.reddit_client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "")
        self.reddit_username = os.environ.get("REDDIT_USERNAME", "")
        self.reddit_password = os.environ.get("REDDIT_PASSWORD", "")
        self.user_agent = os.environ.get(
            "REDDIT_USER_AGENT",
            f"reddit-recall/0.1 by u/{self.reddit_username or 'unknown'}",
        )
        self.model = os.environ.get("RECALL_MODEL", "claude-opus-5")
        # Subreddits scanned in scan mode (comma-separated).
        self.subreddits = [
            s.strip() for s in
            os.environ.get("RECALL_SUBREDDITS", "ClaudeCode,ClaudeAI").split(",")
            if s.strip()
        ]
        # Listing window for scan mode: hour/day/week/month/year/all.
        self.time_filter = os.environ.get("RECALL_TIME_FILTER", "week")
        # Posts scanned per subreddit per run.
        self.post_limit = int(os.environ.get("RECALL_POST_LIMIT", "25"))
        # How many listing pages (of 100 items) to walk per source in history mode.
        self.max_pages = int(os.environ.get("RECALL_MAX_PAGES", "4"))
        # Days after which a surfaced idea that saw no action counts as stale.
        self.stale_days = int(os.environ.get("RECALL_STALE_DAYS", "14"))

    def validate_reddit(self) -> list[str]:
        """Scan mode only needs the app credentials."""
        return [
            name for name in ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET")
            if not os.environ.get(name)
        ]

    def validate_history(self) -> list[str]:
        """History mode additionally needs the account credentials."""
        return self.validate_reddit() + [
            name for name in ("REDDIT_USERNAME", "REDDIT_PASSWORD")
            if not os.environ.get(name)
        ]
