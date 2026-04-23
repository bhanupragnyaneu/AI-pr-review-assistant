## Requirements

```
fastapi
uvicorn
python-dotenv
PyJWT
cryptography
requests
qdrant-client
sentence-transformers
groq
openai
sqlalchemy
streamlit
pandas
tiktoken
```

## Environment variables

| Variable | Description |
|---|---|
| `APP_ID` | Your GitHub App ID (from app settings page) |
| `WEBHOOK_SECRET` | Secret used to verify webhook signatures |
| `PRIVATE_KEY_PATH` | Path to your GitHub App's `.pem` private key file |
| `GROQ_API_KEY` | Groq API key for LLM inference |
| `QDRANT_HOST` | Qdrant host (default: localhost) |
| `QDRANT_PORT` | Qdrant port (default: 6333) |

## Security notes

- Webhook payloads are verified using HMAC-SHA256 before any processing
- GitHub App private key and webhook secret are never committed to version control
- Installation tokens are short-lived (1 hour) and scoped per repository
- The bot requests only the minimum permissions needed (least privilege)
