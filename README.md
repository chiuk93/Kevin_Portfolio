# reddit-recall

Scans the Claude Code subreddits every week, has Claude judge — with a high
bar — which ideas are genuinely worth *your* time to build, and keeps nudging
you until you act on them. No saving or upvoting required.

**The loop:**

```
scan ──▶ judge ──▶ digest ──▶ you implement ──▶ mark done
  │        │          │
  │        │          └─ digests/YYYY-MM-DD.md + BACKLOG.md + GitHub issue
  │        └─ Claude filters hard: "would I honestly spend time building this,
  │           for this user?" — judged against context/profile.md
  └─ top posts of the week (+ best comments) from r/ClaudeCode, r/ClaudeAI
```

**Why it compounds (the recursive part):**

- Every post ever scanned is remembered (`data/items.json`) — nothing is
  judged twice.
- Every idea lives in a status backlog (`data/backlog.json` → `BACKLOG.md`):
  `new → reviewing → implementing → done` (or `rejected`).
- Ideas you mark `rejected` are fed back to the judge as taste signals, so it
  stops surfacing that kind of idea.
- `context/profile.md` describes your stack and priorities and is fed into
  every judgment — sharpen it over time and the picks get better.
- Open ideas untouched for 14 days reappear in the digest as a nudge:
  implement or reject, no silent rot.

## One-time setup

1. **Reddit API credentials** — go to <https://www.reddit.com/prefs/apps>,
   create an app of type **script** (redirect URI can be `http://localhost:8080`).
   Note the client ID (the string under the app name) and the secret.
   That's all scan mode needs — no Reddit password.
2. **Anthropic API key** — from <https://platform.claude.com/>.
3. **Personalize `context/profile.md`** — this is the judging lens; 5 minutes
   here is the highest-leverage step.
4. **Local use:** `cp .env.example .env`, fill it in, then:

   ```bash
   pip install -r requirements.txt
   python -m reddit_recall run
   ```

5. **Scheduled use (recommended):** add three repository secrets under
   *Settings → Secrets and variables → Actions*:

   `REDDIT_CLIENT_ID` · `REDDIT_CLIENT_SECRET` · `ANTHROPIC_API_KEY`

   The workflow (`.github/workflows/reddit-recall.yml`) runs every Monday,
   commits the updated state, and opens a GitHub issue containing the digest —
   that issue is your nudge. Scheduled workflows only fire on the default
   branch, so merge this to `main` (or trigger manually via *Actions →
   reddit-recall → Run workflow* until then).

## Commands

```bash
python -m reddit_recall run              # scan + judge + digest (the usual)
python -m reddit_recall run --history    # also mine your own saved/upvoted items
python -m reddit_recall fetch            # just scan for new posts
python -m reddit_recall extract          # just judge unprocessed posts
python -m reddit_recall digest           # just rewrite digest + BACKLOG.md
python -m reddit_recall list             # show the backlog (highest impact first)
python -m reddit_recall list --status new
python -m reddit_recall mark <id> done   # or: reviewing / implementing / rejected
```

`--history` mode additionally needs `REDDIT_USERNAME` / `REDDIT_PASSWORD`
(2FA accounts: append `:123456` with the current TOTP code — impractical for
scheduled runs, fine locally).

Test the pipeline without any credentials:

```bash
python -m reddit_recall run --fixtures tests/fixtures/reddit_items.json --mock
```

## Where things live

| Path                 | What it is |
|----------------------|------------|
| `BACKLOG.md`         | Human-readable backlog — your reading surface |
| `context/profile.md` | The judging lens — edit this to tune what gets picked |
| `digests/`           | One markdown digest per run that found something |
| `data/items.json`    | Every Reddit post ever scanned (novelty filter) |
| `data/backlog.json`  | The backlog's source of truth (statuses live here) |

State is plain JSON committed to git: diffable, hand-editable, no database.

## Configuration (env vars)

| Variable             | Default             | Meaning |
|----------------------|---------------------|---------|
| `RECALL_MODEL`       | `claude-opus-5`     | Model used for judging/extraction |
| `RECALL_SUBREDDITS`  | `ClaudeCode,ClaudeAI` | Comma-separated subreddits to scan |
| `RECALL_TIME_FILTER` | `week`              | Top-posts window: hour/day/week/month/year/all |
| `RECALL_POST_LIMIT`  | `25`                | Posts per subreddit per run |
| `RECALL_STALE_DAYS`  | `14`                | Days before an untouched open idea gets nudged |
