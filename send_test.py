"""Send a sample event to the local server (signs it if WEBHOOK_SECRET is set)."""
import hashlib
import hmac
import json
import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()
url = os.getenv("WEBHOOK_URL", "http://127.0.0.1:5000/webhook")
path = sys.argv[1] if len(sys.argv) > 1 else "sample_payload.json"

body = open(path, "rb").read()
headers = {"Content-Type": "application/json"}
secret = os.getenv("WEBHOOK_SECRET", "")
if secret:
    headers["X-Signature"] = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

r = requests.post(url, data=body, headers=headers, timeout=30)
print(r.status_code)
print(json.dumps(r.json(), indent=2))
