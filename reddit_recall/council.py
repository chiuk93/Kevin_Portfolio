"""Multi-model council: every extracted idea is scored 1-10 by several Claude
models independently; the mean decides what makes the backlog and how ideas
rank in the app. 9+ means "the council would insist you adopt this"."""

import json

from pydantic import BaseModel, Field

SHORT_NAMES = {
    "claude-opus-5": "opus",
    "claude-sonnet-5": "sonnet",
    "claude-haiku-4-5": "haiku",
}

JUDGE_SYSTEM = """\
You are one judge on a council of AI models scoring workflow ideas for a solo \
developer who uses Claude Code daily to automate personal/business processes.

Score each candidate 1-10 for: (a) general applicability across projects, \
(b) real, lasting workflow impact, (c) concreteness — can it be set up from \
the description, (d) payoff vs setup time.

Be strict and use the full scale. A 9 or 10 means: "I would personally insist \
a colleague adopt this — it pays off within a week and keeps paying off." \
Most decent ideas are 6-8. Grade on merit, not popularity. Rate EVERY \
candidate by its index."""


class Rating(BaseModel):
    index: int = Field(description="The candidate's index as given")
    score: int = Field(description="1-10")


class CouncilResult(BaseModel):
    ratings: list[Rating]


def _short(model: str) -> str:
    return SHORT_NAMES.get(model, model)


def run_council(ideas: list[dict], models: list[str]) -> list[dict]:
    """Attach council scores to each idea (mutates and returns the list)."""
    if not ideas:
        return ideas
    import anthropic

    client = anthropic.Anthropic()
    candidates = [
        {"index": n, "title": i["title"], "summary": i["summary"],
         "first_step": i["first_step"], "effort": i.get("effort", "")}
        for n, i in enumerate(ideas)
    ]
    prompt = "Candidates to score:\n" + json.dumps(candidates, indent=2)

    votes: dict[int, dict[str, int]] = {n: {} for n in range(len(ideas))}
    for model in models:
        try:
            response = client.messages.parse(
                model=model,
                max_tokens=8000,
                system=JUDGE_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
                output_format=CouncilResult,
            )
        except Exception as exc:  # one judge failing shouldn't sink the run
            print(f"  council: {model} failed ({exc}), continuing without it")
            continue
        if response.stop_reason == "refusal" or response.parsed_output is None:
            print(f"  council: {model} returned no usable ratings, skipping")
            continue
        for rating in response.parsed_output.ratings:
            if rating.index in votes:
                votes[rating.index][_short(model)] = max(1, min(10, rating.score))

    for n, idea in enumerate(ideas):
        scores = votes[n]
        if scores:
            idea["council"] = {
                "scores": scores,
                "mean": round(sum(scores.values()) / len(scores), 2),
            }
    return ideas


def mock_council(ideas: list[dict]) -> list[dict]:
    """Deterministic scores for --mock testing."""
    for n, idea in enumerate(ideas):
        scores = {"opus": 9, "sonnet": 8 + (n % 2), "haiku": 9}
        idea["council"] = {
            "scores": scores,
            "mean": round(sum(scores.values()) / len(scores), 2),
        }
    return ideas


def council_mean(idea: dict) -> float:
    return idea.get("council", {}).get("mean", 0.0)
