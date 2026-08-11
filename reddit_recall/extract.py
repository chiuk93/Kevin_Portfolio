"""Idea extraction: Claude reads scanned Reddit posts and judges — with a high
bar — which ideas are genuinely worth this user's time to build or adopt."""

from pydantic import BaseModel, Field

from .config import PROFILE_PATH

BATCH_SIZE = 8

SYSTEM_PROMPT = """\
You are a discerning senior engineer curating ideas for a developer who uses \
Claude Code heavily. You read top Reddit posts (and their best comments) from \
Claude Code / AI-coding subreddits and decide which ideas are GENUINELY worth \
this specific user's time to build or adopt.

The bar is high. Ask yourself for each candidate: "If this were my own \
workflow, would I honestly spend the time to build this — and would it still \
be paying off a month later?" Only ideas that clear that bar go in your output.

Reject without hesitation:
- Hype, memes, model-release news, benchmark screenshots, rants, pricing drama.
- Vague advice with no concrete mechanism ("just prompt better").
- Ideas that only make sense for large teams or stacks the user doesn't run.
- Ideas that duplicate anything in the user's existing backlog (list provided).
  Titles marked (rejected) show what the user has already turned down — treat
  those as taste signals and don't re-surface near-identical ideas.

A typical scan yields 0-5 ideas that clear the bar. Returning ZERO ideas is a
good outcome — it means the week was noise. Never pad.

For ideas that do clear the bar:
- "verdict" is your honest opinion: why this is worth the build time for THIS
  user, given their profile — one or two blunt sentences.
- "first_step" must be doable in under 30 minutes.
- "impact" is 1-5 for THIS user's daily workflow. If you can't defend a 3+,
  the idea probably shouldn't be in your output.
- Set "source_permalink" to the permalink of the Reddit item the idea came from.
"""


class Idea(BaseModel):
    title: str = Field(description="Short imperative title, e.g. 'Add a pre-commit hook that runs /security-review'")
    summary: str = Field(description="2-3 sentences: what the idea is and the mechanism behind it")
    verdict: str = Field(description="1-2 blunt sentences: your honest opinion on why this is worth this user's build time")
    why_it_matters: str = Field(description="1-2 sentences: what it improves for this user's processes")
    first_step: str = Field(description="The concrete first action, doable in under 30 minutes")
    category: str = Field(description="One of: tooling, workflow, prompting, automation, configuration, learning")
    impact: int = Field(description="1-5 estimated impact on this user's daily workflow")
    effort: str = Field(description="One of: low, medium, high")
    source_permalink: str = Field(description="Permalink of the Reddit item this came from")
    tags: list[str] = Field(description="2-4 short lowercase tags")


class ExtractionResult(BaseModel):
    ideas: list[Idea]


def load_profile() -> str:
    if PROFILE_PATH.exists():
        return PROFILE_PATH.read_text().strip()
    return "(no profile yet — judge for a solo developer who uses Claude Code daily)"


def _format_items(items: list[dict]) -> str:
    blocks = []
    for item in items:
        blocks.append(
            f"### [{item['id']}] r/{item['subreddit']} ({', '.join(item['sources'])}, score {item.get('score', '?')})\n"
            f"Title: {item['title']}\n"
            f"Permalink: {item['permalink']}\n"
            f"Link: {item.get('link', '')}\n"
            f"Body:\n{item['body'] or '(no text body)'}"
        )
    return "\n\n".join(blocks)


def _titles_block(existing: list[str], new_this_run: list[dict]) -> str:
    lines = existing + [i["title"] for i in new_this_run]
    return "\n".join(f"- {t}" for t in lines) or "(backlog is empty)"


def extract_ideas(items: list[dict], existing_titles: list[str],
                  model: str) -> list[dict]:
    """Run Claude over items in batches; return only ideas that clear the bar."""
    import anthropic

    client = anthropic.Anthropic()
    profile = load_profile()
    all_ideas: list[dict] = []
    for start in range(0, len(items), BATCH_SIZE):
        batch = items[start:start + BATCH_SIZE]
        user_prompt = (
            "## User profile (judge against this)\n"
            f"{profile}\n\n"
            "## Existing backlog titles (do NOT duplicate; '(rejected)' = user turned it down)\n"
            f"{_titles_block(existing_titles, all_ideas)}\n\n"
            "## Reddit items to judge\n\n"
            f"{_format_items(batch)}"
        )
        response = client.messages.parse(
            model=model,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
            output_format=ExtractionResult,
        )
        if response.stop_reason == "refusal":
            print(f"  batch starting at {start}: model refused, skipping")
            continue
        result = response.parsed_output
        if result is None:
            print(f"  batch starting at {start}: could not parse output, skipping")
            continue
        all_ideas.extend(idea.model_dump() for idea in result.ideas)
    return all_ideas


def extract_ideas_mock(items: list[dict], existing_titles: list[str],
                       model: str = "") -> list[dict]:
    """Deterministic no-API extractor for local testing (--mock)."""
    existing = set(existing_titles)
    ideas = []
    for item in items:
        title = f"Try: {item['title'][:50]}"
        if title in existing:
            continue
        ideas.append({
            "title": title,
            "summary": (item["body"] or item["title"])[:200],
            "verdict": "Mock verdict: looks plausibly useful.",
            "why_it_matters": "Mock extraction for local testing.",
            "first_step": f"Read {item['permalink']}",
            "category": "workflow",
            "impact": 3,
            "effort": "low",
            "source_permalink": item["permalink"],
            "tags": ["mock"],
        })
    return ideas
