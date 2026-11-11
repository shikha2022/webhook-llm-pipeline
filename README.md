# Webhook → S3 → LLM summary pipeline

A small integration service: it receives webhook events, verifies them, ignores duplicates, stores the raw payload (S3 or local), and adds a short LLM-written summary.

```
Sender ──POST /webhook──▶ verify signature ─▶ dedupe by event_id ─▶ store raw JSON (S3 / ./data)
                                                                   └▶ LLM summary ─▶ 200 response
```

## Why it's built this way
- **Signature check (HMAC-SHA256):** only trusted senders can post events.
- **Idempotency:** senders retry, so repeated `event_id`s return `duplicate` instead of being processed twice.
- **Raw payload stored first:** you can always replay an event, even if the summary step fails.
- **LLM errors never fail the webhook:** the sender gets a 200 and the error is logged, so a model outage doesn't trigger a retry storm.
- **S3 uploads retry with backoff.**

## Run it (no API key or AWS needed)
```bash
python -m venv venv && source venv/bin/activate     # Windows: venv\Scripts\activate
pip install flask python-dotenv requests boto3
cp .env.example .env                                  # defaults to LLM_PROVIDER=mock
python app.py                                         # terminal 1
python send_test.py                                   # terminal 2
python send_test.py bad_payload.json                  # broken event: see the checks flag it
```
Run `send_test.py` twice to see the duplicate handling. Events appear under `./data/events/`.The bad payload has no `country` and a negative `revenue`, so the summary should flag both.

## Turn on the real pieces
- **LLM:** `pip install anthropic` (or `openai`), then set `LLM_PROVIDER` and the matching API key in `.env`. For OpenAI also set `LLM_MODEL`. API calls are billed by the provider, so check pricing first.
- **S3:** set `S3_BUCKET` and AWS credentials (or use `aws configure`). Use a bucket and IAM user created just for this project.

## Roadmap (next projects reuse this)
- [ ] Unit tests for signature, duplicate and error paths
- [ ] Replace the JSON seen-file with a small database
- [ ] Project 2: RAG over integration docs
- [ ] Project 3: MCP server exposing this service as tools
- [ ] Project 4: agent that diagnoses failing webhooks
