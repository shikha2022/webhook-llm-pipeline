"""One-paragraph summary of a webhook event.

LLM_PROVIDER=mock       -> no API key needed, simple rule-based summary (default)
LLM_PROVIDER=anthropic  -> needs ANTHROPIC_API_KEY (LLM_MODEL optional)
LLM_PROVIDER=openai     -> needs OPENAI_API_KEY and LLM_MODEL
"""
import json
import os

PROMPT = (
    "You are an integration support engineer. Summarise this webhook event in 2 sentences "
    "for a customer: what happened, and anything that looks wrong or worth checking.\n\n{event}"
)


def summarize(payload: dict) -> str:
    provider = os.getenv("LLM_PROVIDER", "mock").lower()
    event = json.dumps(payload, indent=2)

    if provider == "mock":
        keys = ", ".join(sorted(payload))
        kind = payload.get("event_type", "unknown event")
        return f"[mock] Received '{kind}' with fields: {keys}."

    if provider == "anthropic":
        import anthropic

        client = anthropic.Anthropic()
        msg = client.messages.create(
            model=os.getenv("LLM_MODEL", "claude-haiku-5-5"),
            max_tokens=300,
            messages=[{"role": "user", "content": PROMPT.format(event=event)}],
        )
        return msg.content[0].text.strip()

    if provider == "openai":
        from openai import OpenAI

        client = OpenAI()
        resp = client.chat.completions.create(
            model=os.environ["LLM_MODEL"],
            messages=[{"role": "user", "content": PROMPT.format(event=event)}],
        )
        return resp.choices[0].message.content.strip()

    raise ValueError(f"Unknown LLM_PROVIDER: {provider}")
