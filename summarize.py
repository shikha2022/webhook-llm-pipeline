"""One-paragraph summary of a webhook event.

LLM_PROVIDER=mock       -> no API key needed, simple rule-based summary (default)
LLM_PROVIDER=anthropic  -> needs ANTHROPIC_API_KEY (LLM_MODEL optional)
LLM_PROVIDER=openai     -> needs OPENAI_API_KEY and LLM_MODEL
"""
import json
import os
from datetime import datetime, timezone

REQUIRED_FIELDS = [
    "event_id", "event_type", "app", "partner",
    "campaign", "platform", "country", "revenue", "timestamp",
]

PROMPT = (
    "You are an integration support engineer. Today's date is {today} (UTC). "
    "Summarise this webhook event in 2 sentences for a customer: what happened, "
    "and anything that looks wrong or worth checking. "
    "Mention every item under 'Automated checks found'.\n\n"
    "Automated checks found: {problems}\n\n{event}"
)


def check_event(payload: dict) -> list:
    """Exact rule checks done in code, so they never depend on the model."""
    problems = []
    for field in REQUIRED_FIELDS:
        if payload.get(field) in (None, ""):
            problems.append(f"missing field '{field}'")
    revenue = payload.get("revenue")
    if isinstance(revenue, (int, float)) and revenue < 0:
        problems.append(f"negative revenue ({revenue})")
    if isinstance(revenue, (int, float)) and revenue != 0 and not payload.get("currency"):
        problems.append("revenue is set but 'currency' is missing")
    return problems


def summarize(payload: dict) -> str:
    provider = os.getenv("LLM_PROVIDER", "mock").lower()
    event = json.dumps(payload, indent=2)
    problems = check_event(payload)
    prompt = PROMPT.format(
        today=datetime.now(timezone.utc).strftime("%d %B %Y"),
        problems="; ".join(problems) or "none",
        event=event,
    )

    if provider == "mock":
        kind = payload.get("event_type", "unknown event")
        return f"[mock] Received '{kind}'. Checks: {'; '.join(problems) or 'none'}."

    if provider == "anthropic":
        import anthropic

        client = anthropic.Anthropic()
        msg = client.messages.create(
            model=os.getenv("LLM_MODEL", "claude-haiku-5-5"),
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in msg.content if b.type == "text").strip()

    if provider == "openai":
        from openai import OpenAI

        client = OpenAI()
        resp = client.chat.completions.create(
            model=os.environ["LLM_MODEL"],
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content.strip()

    raise ValueError(f"Unknown LLM_PROVIDER: {provider}")