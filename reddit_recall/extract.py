"""Idea extraction: turn raw Reddit items into actionable backlog entries via Claude."""

from pydantic import BaseModel, Field

BATCH_SIZE = 8

SYSTEM_PROMPT = """\
You are an idea miner for a developer who uses Claude Code heavily. You read \
their saved/upvoted Reddit posts and comments (mostly from r/ClaudeCode, \
r/ClaudeAI, and adjacent programming subreddits) and extract concrete, \
actionable items they could adopt: tools to install, workflows to set up, \
configuration tips, prompting techniques, automation ideas, MCP servers, \
hooks, slash commands, and process improvements.

Rules:
- Extract only genuinely actionable ideas. Memes, opinion threads, news, and \
vague hype produce nothing — return zero ideas for those rather than padding.
- One Reddit item can yield zero, one, or several ideas.
- Skip anything that duplicates an idea already in the user's backlog \
(a list of existing idea titles is provided).
- Be concrete: "first_step" must be something doable in under 30 minutes.
- "impact" is 1-5: how much this could improve the user's daily Claude Code \
workflow. Be honest — most tips are a 2 or 3.
- Set "source_permalink" to the permalink of the Reddit item the idea came from.
"""


class Idea(BaseModel):
    title: str = Field(description="Short imperative title, e.g. 'Add a pre-commit hook that runs /security-review'")
    summary: str = Field(description="2-3 sentences: what the idea is")
    why_it_matters: str = Field(description="1-2 sentences: what it improves for this user")
    first_step: str = Field(description="The concrete first action, doable in under 30 minutes")
    category: str = Field(description="One of: tooling, workflow, prompting, automation, configuration, learning")
    impact: int = Field(description="1-5 estimated impact on daily workflow")
    effort: str = Field(description="One of: low, medium, high")
    source_permalink: str = Field(description="Permalink of the Reddit item this came from")
    tags: list[str] = Field(description="2-4 short lowercase tags")


class ExtractionResult(BaseModel):
    ideas: list[Idea]


def _format_items(items: list[dict]) -> str:
    blocks = []
    for item in items:
        blocks.append(
            f"### [{item['id']}] r/{item['subreddit']} ({', '.join(item['sources'])})\n"
            f"Title: {item['title']}\n"
            f"Permalink: {item['permalink']}\n"
            f"Link: {item.get('link', '')}\n"
            f"Body:\n{item['body'] or '(no text body)'}"
        )
    return "\n\n".join(blocks)


def extract_ideas(items: list[dict], existing_titles: list[str],
                  model: str) -> list[dict]:
    """Run Claude over items in batches; return new idea dicts."""
    import anthropic

    client = anthropic.Anthropic()
    all_ideas: list[dict] = []
    for start in range(0, len(items), BATCH_SIZE):
        batch = items[start:start + BATCH_SIZE]
        titles_block = "\n".join(f"- {t}" for t in existing_titles + [i["title"] for i in all_ideas]) or "(backlog is empty)"
        user_prompt = (
            "Existing backlog idea titles (do NOT duplicate these):\n"
            f"{titles_block}\n\n"
            "Reddit items to mine:\n\n"
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
            "why_it_matters": "Mock extraction for local testing.",
            "first_step": f"Read {item['permalink']}",
            "category": "workflow",
            "impact": 3,
            "effort": "low",
            "source_permalink": item["permalink"],
            "tags": ["mock"],
        })
    return ideas
