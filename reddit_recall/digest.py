"""Digest generation: the weekly markdown report and the living BACKLOG.md."""

from datetime import datetime, timezone

from .config import BACKLOG_MD, DIGEST_DIR
from .store import OPEN_STATUSES, Backlog

STATUS_EMOJI = {
    "new": "🆕",
    "reviewing": "🔍",
    "implementing": "🔨",
    "done": "✅",
    "rejected": "🚫",
}


def _idea_block(idea: dict) -> str:
    return (
        f"### {idea['title']}\n"
        f"`{idea['id']}` · impact {idea['impact']}/5 · {idea['effort']} effort · {idea['category']}\n\n"
        f"{idea['summary']}\n\n"
        f"**Verdict:** {idea.get('verdict', '')}\n\n"
        f"**Why it matters:** {idea['why_it_matters']}\n\n"
        f"**First step:** {idea['first_step']}\n\n"
        f"**Source:** {idea['source_permalink']}\n"
    )


def write_digest(new_ideas: list[dict], stale_ideas: list[dict],
                 backlog: Backlog) -> str | None:
    """Write digests/YYYY-MM-DD.md. Returns the path, or None if nothing to say."""
    if not new_ideas and not stale_ideas:
        return None

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [f"# Reddit Recall digest — {today}", ""]

    if new_ideas:
        ranked = sorted(new_ideas, key=lambda i: -i["impact"])
        lines += [f"## {len(ranked)} new idea(s) from your Reddit history", ""]
        for idea in ranked:
            lines += [_idea_block(idea), ""]

    if stale_ideas:
        lines += ["## Nudge: ideas going stale", "",
                  "These were surfaced earlier but haven't moved. Implement, or mark "
                  "them `rejected` so they stop nagging:", ""]
        for idea in stale_ideas:
            lines.append(
                f"- {STATUS_EMOJI[idea['status']]} `{idea['id']}` — {idea['title']} "
                f"(status `{idea['status']}` since {idea['updated_at'][:10]})"
            )
        lines.append("")

    counts = _status_counts(backlog)
    lines += ["## Backlog snapshot", "",
              " · ".join(f"{STATUS_EMOJI[s]} {s}: {n}" for s, n in counts.items() if n), "",
              "Update statuses with: `python -m reddit_recall mark <id> <status>`", ""]

    DIGEST_DIR.mkdir(parents=True, exist_ok=True)
    path = DIGEST_DIR / f"{today}.md"
    path.write_text("\n".join(lines))
    return str(path)


def write_backlog_md(backlog: Backlog) -> str:
    """Regenerate BACKLOG.md — the human-readable view of data/backlog.json."""
    lines = ["# Idea Backlog", "",
             "Mined from Reddit by [reddit-recall](README.md). "
             "Statuses: new → reviewing → implementing → done (or rejected).", ""]

    open_ideas = [i for i in backlog.ideas if i["status"] in OPEN_STATUSES]
    closed = [i for i in backlog.ideas if i["status"] not in OPEN_STATUSES]

    if open_ideas:
        lines += ["## Open", "", "| | id | idea | impact | effort | status |",
                  "|---|---|---|---|---|---|"]
        for i in sorted(open_ideas, key=lambda x: -x["impact"]):
            lines.append(
                f"| {STATUS_EMOJI[i['status']]} | `{i['id']}` "
                f"| [{i['title']}]({i['source_permalink']}) "
                f"| {i['impact']}/5 | {i['effort']} | {i['status']} |"
            )
        lines.append("")
        lines += ["### Details", ""]
        for i in sorted(open_ideas, key=lambda x: -x["impact"]):
            lines += [_idea_block(i), ""]

    if closed:
        lines += ["## Closed", "", "| | id | idea | status |", "|---|---|---|---|"]
        for i in closed:
            lines.append(
                f"| {STATUS_EMOJI[i['status']]} | `{i['id']}` | {i['title']} | {i['status']} |"
            )
        lines.append("")

    if not backlog.ideas:
        lines += ["_Backlog is empty — run `python -m reddit_recall run` to mine ideas._", ""]

    BACKLOG_MD.write_text("\n".join(lines))
    return str(BACKLOG_MD)


def _status_counts(backlog: Backlog) -> dict[str, int]:
    counts = {s: 0 for s in STATUS_EMOJI}
    for idea in backlog.ideas:
        counts[idea["status"]] = counts.get(idea["status"], 0) + 1
    return counts
