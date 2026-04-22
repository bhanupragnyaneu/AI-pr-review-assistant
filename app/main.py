import hmac
import hashlib
import os
from fastapi import FastAPI, Request, HTTPException
from dotenv import load_dotenv
from app.handlers.pull_request import handle_pull_request

load_dotenv()

app = FastAPI()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")

def verify_signature(payload: bytes, signature: str) -> bool:
    expected = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)

@app.get("/")
def root():
    return {"status": "code-review-bot running"}

@app.post("/webhook")
async def webhook(request: Request):
    payload_bytes = await request.body()
    sig = request.headers.get("X-Hub-Signature-256", "")

    if not verify_signature(payload_bytes, sig):
        raise HTTPException(status_code=401, detail="Invalid signature")

    event = request.headers.get("X-GitHub-Event")
    payload = await request.json()

    print(f"📦 Event received: {event}, action: {payload.get('action')}")

    if event == "pull_request" and payload.get("action") in ("opened", "synchronize"):
        await handle_pull_request(payload)

    return {"ok": True}