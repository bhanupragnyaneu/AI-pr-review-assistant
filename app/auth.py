import time
import jwt
import requests
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

APP_ID = os.getenv("APP_ID")
PRIVATE_KEY = Path(os.getenv("PRIVATE_KEY_PATH", "private-key.pem")).read_text()

def generate_jwt() -> str:
    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + 600,
        "iss": APP_ID,
    }
    return jwt.encode(payload, PRIVATE_KEY, algorithm="RS256")

def get_installation_token(installation_id: int) -> str:
    token = generate_jwt()
    url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
    resp = requests.post(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    })
    resp.raise_for_status()
    return resp.json()["token"]