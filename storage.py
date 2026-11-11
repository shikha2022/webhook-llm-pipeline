"""Save raw payloads to S3 when S3_BUCKET is set, otherwise to ./data/ locally."""
import logging
import os
import time
from pathlib import Path

log = logging.getLogger("storage")
RETRIES = 3


def save_payload(key: str, body: bytes) -> str:
    bucket = os.getenv("S3_BUCKET")
    if not bucket:
        path = Path("data") / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        return str(path)

    import boto3  # imported lazily so local runs don't need AWS set up

    s3 = boto3.client("s3")
    for attempt in range(1, RETRIES + 1):
        try:
            s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json")
            return f"s3://{bucket}/{key}"
        except Exception:
            log.warning("S3 upload failed (attempt %d/%d)", attempt, RETRIES)
            if attempt == RETRIES:
                raise
            time.sleep(2 ** attempt)  # simple exponential backoff
