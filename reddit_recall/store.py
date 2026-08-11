"""Git-friendly JSON persistence: seen items and the idea backlog.

Everything lives in data/*.json so state is diffable, human-editable,
and survives across runs by being committed to the repo.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .config import DATA_DIR

ITEMS_PATH = DATA_DIR / "items.json"
BACKLOG_PATH = DATA_DIR / "backlog.json"

STATUSES = ("new", "reviewing", "implementing", "done", "rejected")
# Statuses that still need action and can go stale.
OPEN_STATUSES = ("new", "reviewing", "implementing")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load(path: Path, default):
    if path.exists():
        return json.loads(path.read_text())
    return default


def _save(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:60] or "idea"


class ItemStore:
    """Tracks every Reddit item we've ever seen, and whether it was extracted."""

    def __init__(self) -> None:
        self.items: dict[str, dict] = _load(ITEMS_PATH, {})

    def add_new(self, fetched: list[dict]) -> list[dict]:
        """Record fetched items; return only the ones we've never seen."""
        fresh = []
        for item in fetched:
            if item["id"] not in self.items:
                self.items[item["id"]] = {**item, "fetched_at": _now(), "extracted": False}
                fresh.append(item)
        return fresh

    def pending_extraction(self) -> list[dict]:
        return [i for i in self.items.values() if not i.get("extracted")]

    def mark_extracted(self, item_ids: list[str]) -> None:
        for item_id in item_ids:
            if item_id in self.items:
                self.items[item_id]["extracted"] = True

    def save(self) -> None:
        _save(ITEMS_PATH, self.items)


class Backlog:
    """The persistent idea backlog with lifecycle statuses."""

    def __init__(self) -> None:
        self.ideas: list[dict] = _load(BACKLOG_PATH, [])

    def existing_titles(self) -> list[str]:
        """Titles for dedup; rejected ones are marked so the judge learns taste."""
        return [
            f"{i['title']} (rejected)" if i["status"] == "rejected" else i["title"]
            for i in self.ideas
        ]

    def _unique_id(self, title: str) -> str:
        base = slugify(title)
        taken = {i["id"] for i in self.ideas}
        candidate, n = base, 2
        while candidate in taken:
            candidate, n = f"{base}-{n}", n + 1
        return candidate

    def add(self, idea: dict) -> dict:
        entry = {
            "id": self._unique_id(idea["title"]),
            "status": "new",
            "created_at": _now(),
            "updated_at": _now(),
            **idea,
        }
        self.ideas.append(entry)
        return entry

    def get(self, idea_id: str) -> dict | None:
        return next((i for i in self.ideas if i["id"] == idea_id), None)

    def mark(self, idea_id: str, status: str) -> dict:
        if status not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}")
        idea = self.get(idea_id)
        if idea is None:
            raise KeyError(f"no idea with id '{idea_id}'")
        idea["status"] = status
        idea["updated_at"] = _now()
        return idea

    def open_ideas(self) -> list[dict]:
        return [i for i in self.ideas if i["status"] in OPEN_STATUSES]

    def stale_ideas(self, stale_days: int) -> list[dict]:
        """Open ideas that haven't moved in `stale_days` days — the nudge list."""
        now = datetime.now(timezone.utc)
        stale = []
        for idea in self.open_ideas():
            updated = datetime.strptime(idea["updated_at"], "%Y-%m-%dT%H:%M:%SZ")
            updated = updated.replace(tzinfo=timezone.utc)
            if (now - updated).days >= stale_days:
                stale.append(idea)
        return stale

    def save(self) -> None:
        _save(BACKLOG_PATH, self.ideas)
