# reddit-recall

Mines your Reddit history for Claude Code tips, tools, and workflows you saved
or upvoted but never implemented — then keeps nudging you until you act on them.

**The loop:**

```
fetch ──▶ extract ──▶ digest ──▶ you implement ──▶ mark done
  │          │           │
  │          │           └─ digests/YYYY-MM-DD.md + BACKLOG.md + GitHub issue
  │          └─ Claude turns raw posts into actionable ideas (deduped vs backlog)
  └─ saved / upvoted / submitted / comments via the Reddit API
```

Every run remembers what it has already seen (`data/items.json`) and what it
already surfaced (`data/backlog.json`), so nothing is shown twice. Ideas move
through statuses — `new → reviewing → implementing → done` (or `rejected`) —
and open ideas that sit untouched for 14 days show up in the next digest as a
nudge. A weekly GitHub Actions run keeps the whole thing going without you.

## One-time setup

1. **Reddit API credentials** — go to <https://www.reddit.com/prefs/apps>,
   create an app of type **script** (redirect URI can be `http://localhost:8080`).
   Note the client ID (under the app name) and secret.
2. **Anthropic API key** — from <https://platform.claude.com/>.
3. **Local use:** `cp .env.example .env`, fill it in, then:

   ```bash
   pip install -r requirements.txt
   python -m reddit_recall run
   ```

4. **Scheduled use (recommended):** add these five repository secrets under
   *Settings → Secrets and variables → Actions*:

   `REDDIT_CLIENT_ID` · `REDDIT_CLIENT_SECRET` · `REDDIT_USERNAME` ·
   `REDDIT_PASSWORD` · `ANTHROPIC_API_KEY`

   The workflow (`.github/workflows/reddit-recall.yml`) runs every Monday,
   commits the updated state, and opens a GitHub issue containing the digest —
   that issue is your nudge. Scheduled workflows only fire on the default
   branch, so merge this to `main` (or trigger manually via *Actions → 
   reddit-recall → Run workflow* until then).

> **2FA note:** the Reddit script-app password grant needs
> `REDDIT_PASSWORD=yourpassword:123456` (current TOTP code appended), which is
> impractical for a scheduled job. If you use 2FA, consider a dedicated
> non-2FA Reddit account for the API app, or run the tool locally.

> **What gets captured:** Reddit's API exposes your saved, upvoted, submitted,
> and commented items — not raw browsing history. Habit to build: **save or
> upvote anything you might want to implement.** That's the capture gesture.

## Commands

```bash
python -m reddit_recall run              # fetch + extract + digest (the usual)
python -m reddit_recall fetch            # just pull new Reddit items
python -m reddit_recall extract          # just run Claude on unprocessed items
python -m reddit_recall digest           # just rewrite digest + BACKLOG.md
python -m reddit_recall list             # show the backlog (highest impact first)
python -m reddit_recall list --status new
python -m reddit_recall mark <id> done   # or: reviewing / implementing / rejected
```

Test the pipeline without any credentials:

```bash
python -m reddit_recall run --fixtures tests/fixtures/reddit_items.json --mock
```

## Where things live

| Path                | What it is |
|---------------------|------------|
| `BACKLOG.md`        | Human-readable backlog — your reading surface |
| `digests/`          | One markdown digest per run that found something |
| `data/items.json`   | Every Reddit item ever seen (novelty filter) |
| `data/backlog.json` | The backlog's source of truth (statuses live here) |

State is plain JSON committed to git: diffable, hand-editable, no database.

## Configuration (env vars)

| Variable            | Default         | Meaning |
|---------------------|-----------------|---------|
| `RECALL_MODEL`      | `claude-opus-5` | Model used for idea extraction |
| `RECALL_MAX_PAGES`  | `4`             | Listing pages (×100 items) per source per run |
| `RECALL_STALE_DAYS` | `14`            | Days before an untouched open idea gets nudged |
