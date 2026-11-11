"""Webhook receiver: verify -> dedupe -> store raw payload -> LLM summary."""
import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request

load_dotenv()

from storage import save_payload  # noqa: E402  (after load_dotenv so env is ready)
from summarize import summarize  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("webhook")

app = Flask(__name__)
SECRET = os.getenv("WEBHOOK_SECRET", "")
SEEN_FILE = Path(os.getenv("SEEN_FILE", "data/seen_events.json"))


def load_seen() -> set:
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text()))
    return set()


def mark_seen(seen: set, event_id: str) -> None:
    seen.add(event_id)
    SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    SEEN_FILE.write_text(json.dumps(sorted(seen)))


def signature_ok(raw_body: bytes) -> bool:
    """If WEBHOOK_SECRET is set, require a valid HMAC-SHA256 in X-Signature."""
    if not SECRET:
        return True
    expected = hmac.new(SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, request.headers.get("X-Signature", ""))


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/webhook")
def webhook():
    raw = request.get_data()

    if not signature_ok(raw):
        return jsonify(error="invalid signature"), 401

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="body must be a JSON object"), 400

    # Idempotency: senders retry, so the same event can arrive more than once.
    event_id = str(payload.get("event_id") or hashlib.sha256(raw).hexdigest())
    seen = load_seen()
    if event_id in seen:
        log.info("duplicate event %s ignored", event_id)
        return jsonify(status="duplicate", event_id=event_id), 200

    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    location = save_payload(f"events/{day}/{event_id}.json", raw)

    # An LLM failure must not make the sender retry, so we log it and still return 200.
    try:
        summary = summarize(payload)
    except Exception:
        log.exception("summary failed for %s", event_id)
        summary = None

    mark_seen(seen, event_id)
    log.info("processed %s -> %s", event_id, location)
    return jsonify(status="ok", event_id=event_id, stored_at=location, summary=summary), 200


if __name__ == "__main__":
    app.run(port=int(os.getenv("PORT", "5000")), debug=True)
