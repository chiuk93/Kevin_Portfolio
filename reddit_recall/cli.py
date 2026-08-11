"""Command-line interface for reddit-recall."""

import argparse
import json
import sys
from pathlib import Path

from .config import Config
from .digest import write_backlog_md, write_digest
from .store import STATUSES, Backlog, ItemStore


def cmd_fetch(args, cfg: Config) -> int:
    store = ItemStore()
    if args.fixtures:
        fetched = json.loads(Path(args.fixtures).read_text())
        print(f"Loaded {len(fetched)} item(s) from fixtures {args.fixtures}")
    else:
        use_history = getattr(args, "history", False)
        missing = cfg.validate_history() if use_history else cfg.validate_reddit()
        if missing:
            print(f"Missing Reddit credentials: {', '.join(missing)}", file=sys.stderr)
            print("Copy .env.example to .env and fill them in (see README).", file=sys.stderr)
            return 1
        from .reddit import RedditClient
        client = RedditClient(
            cfg.reddit_client_id, cfg.reddit_client_secret, cfg.user_agent,
            username=cfg.reddit_username if use_history else "",
            password=cfg.reddit_password if use_history else "",
            max_pages=cfg.max_pages,
        )
        fetched = client.fetch_subreddits(
            cfg.subreddits, cfg.time_filter, cfg.post_limit
        )
        print(f"Scanned {len(fetched)} post(s) from {', '.join('r/' + s for s in cfg.subreddits)} "
              f"(top of the {cfg.time_filter})")
        if use_history:
            history = client.fetch_history()
            print(f"Fetched {len(history)} item(s) from your own Reddit history")
            fetched.extend(history)
    fresh = store.add_new(fetched)
    store.save()
    print(f"{len(fresh)} new item(s) recorded, {len(store.pending_extraction())} pending extraction")
    return 0


def cmd_extract(args, cfg: Config) -> int:
    store = ItemStore()
    backlog = Backlog()
    pending = store.pending_extraction()
    if not pending:
        print("Nothing pending extraction.")
        return 0
    print(f"Extracting ideas from {len(pending)} item(s) with {'mock extractor' if args.mock else cfg.model}...")
    if args.mock:
        from .extract import extract_ideas_mock as extractor
    else:
        from .extract import extract_ideas as extractor
    ideas = extractor(pending, backlog.existing_titles(), cfg.model)
    added = [backlog.add(i) for i in ideas]
    store.mark_extracted([i["id"] for i in pending])
    backlog.save()
    store.save()
    print(f"Added {len(added)} new idea(s) to the backlog:")
    for idea in added:
        print(f"  [{idea['impact']}/5] {idea['id']}: {idea['title']}")
    return 0


def cmd_digest(args, cfg: Config) -> int:
    backlog = Backlog()
    new_ideas = [i for i in backlog.ideas if i["status"] == "new"]
    stale = [i for i in backlog.stale_ideas(cfg.stale_days) if i["status"] != "new"]
    path = write_digest(new_ideas, stale, backlog)
    write_backlog_md(backlog)
    if path:
        print(f"Digest written: {path}")
        print("BACKLOG.md updated")
    else:
        print("Nothing new and nothing stale — no digest written. BACKLOG.md updated")
    return 0


def cmd_run(args, cfg: Config) -> int:
    rc = cmd_fetch(args, cfg)
    if rc != 0:
        return rc
    rc = cmd_extract(args, cfg)
    if rc != 0:
        return rc
    return cmd_digest(args, cfg)


def cmd_mark(args, cfg: Config) -> int:
    backlog = Backlog()
    try:
        idea = backlog.mark(args.id, args.status)
    except (KeyError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    backlog.save()
    write_backlog_md(backlog)
    print(f"{idea['id']} -> {idea['status']}")
    return 0


def cmd_list(args, cfg: Config) -> int:
    backlog = Backlog()
    ideas = backlog.ideas
    if args.status:
        ideas = [i for i in ideas if i["status"] == args.status]
    if not ideas:
        print("(no ideas)")
        return 0
    for idea in sorted(ideas, key=lambda i: -i["impact"]):
        print(f"[{idea['status']:>12}] [{idea['impact']}/5] {idea['id']}: {idea['title']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reddit_recall",
        description="Mine your Reddit history for Claude Code ideas you never implemented.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_fetch = sub.add_parser("fetch", help="Scan subreddits for top posts (default) and optionally your own history")
    p_fetch.add_argument("--fixtures", help="Load items from a JSON file instead of the Reddit API")
    p_fetch.add_argument("--history", action="store_true",
                         help="Also pull your saved/upvoted/submitted/comments (needs username+password)")

    p_extract = sub.add_parser("extract", help="Judge unprocessed items and extract ideas worth building")
    p_extract.add_argument("--mock", action="store_true", help="Use the no-API mock extractor")

    sub.add_parser("digest", help="Write the digest and regenerate BACKLOG.md")

    p_run = sub.add_parser("run", help="fetch + extract + digest in one go")
    p_run.add_argument("--fixtures", help="Load items from a JSON file instead of the Reddit API")
    p_run.add_argument("--history", action="store_true",
                       help="Also pull your own Reddit history (needs username+password)")
    p_run.add_argument("--mock", action="store_true", help="Use the no-API mock extractor")

    p_mark = sub.add_parser("mark", help="Update an idea's status")
    p_mark.add_argument("id")
    p_mark.add_argument("status", choices=STATUSES)

    p_list = sub.add_parser("list", help="List backlog ideas")
    p_list.add_argument("--status", choices=STATUSES)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = Config()
    handler = {
        "fetch": cmd_fetch,
        "extract": cmd_extract,
        "digest": cmd_digest,
        "run": cmd_run,
        "mark": cmd_mark,
        "list": cmd_list,
    }[args.command]
    return handler(args, cfg)
