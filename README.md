# PR Review Assistant

A GitHub App that automatically reviews pull requests using RAG over your codebase, AST-based impact analysis, and an LLM — with an evaluation harness that measures suggestion precision over time.

## What it does

When a pull request is opened or updated, the bot:

1. Receives a signed webhook event from GitHub
2. Parses the diff into structured hunks and identifies changed files
3. Clones the repo and builds an AST-based import graph to trace which modules are impacted by the change
4. Indexes the codebase into a vector database and retrieves the most semantically relevant code chunks
5. Sends the diff, impact analysis, and retrieved context to an LLM to generate a structured review
6. Posts the review as a comment directly on the PR (editing the existing comment on re-push, never spamming)
7. Saves the review to a local database for evaluation

## Architecture

```
GitHub PR event
      │
      ▼
FastAPI webhook receiver
  └── signature verification (HMAC-SHA256)
      │
      ▼
Diff parser
  └── extracts changed files and line hunks
      │
      ▼
Impact analyzer
  └── AST-based import graph (Python ast module)
  └── finds all files that import the changed modules
  └── suggests relevant test files
      │
      ▼
RAG pipeline
  └── clones repo (shallow, depth=1)
  └── chunks by function/class boundary
  └── embeds with all-MiniLM-L6-v2 (local, no API cost)
  └── stores in Qdrant vector DB
  └── retrieves top-k most relevant chunks
      │
      ▼
LLM review (Groq / llama-3.1-8b-instant)
  └── structured JSON output: summary, risks, suggestions, test coverage
      │
      ▼
GitHub commenter
  └── deduplicates (edit existing comment, don't create new ones)
  └── exponential backoff on rate limits
      │
      ▼
Evaluation database (SQLite)
  └── stores every review and suggestion
  └── Streamlit dashboard for labeling + precision tracking
```

## Tech stack

| Component | Technology |
|---|---|
| Web framework | FastAPI + uvicorn |
| GitHub integration | GitHub Apps (JWT + installation tokens) |
| AST parsing | Python `ast` module |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (local) |
| Vector database | Qdrant |
| LLM | Groq API (`llama-3.1-8b-instant`) |
| Evaluation database | SQLite via SQLAlchemy |
| Eval dashboard | Streamlit |

## Project structure

```
code-review-assistant/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app, webhook receiver, signature verification
│   ├── auth.py              # GitHub App JWT generation + installation token exchange
│   ├── diff_parser.py       # Unified diff parser → structured hunks
│   ├── impact_analyzer.py   # AST import graph + impact tracing + test file detection
│   ├── chunker.py           # Repo walker — chunks code by function/class boundary
│   ├── rag.py               # Embedding, Qdrant indexing, retrieval, LLM review generation
│   ├── commenter.py         # GitHub PR comment posting with deduplication + backoff
│   ├── database.py          # SQLAlchemy models + review/label persistence
│   └── handlers/
│       ├── __init__.py
│       └── pull_request.py  # Orchestrates the full pipeline per PR event
├── dashboard.py             # Streamlit evaluation dashboard
├── reviews.db               # SQLite database (auto-created)
├── .env                     # Environment variables (not committed)
├── private-key.pem          # GitHub App private key (not committed)
└── README.md
```

## Setup

### Prerequisites

- Python 3.10+
- Docker (for Qdrant)
- ngrok (for local webhook development)
- A GitHub account

### 1. Register a GitHub App

1. Go to **GitHub → Settings → Developer Settings → GitHub Apps → New GitHub App**
2. Set permissions:
   - Contents: Read-only
   - Pull requests: Read & Write
   - Issues: Read-only
   - Metadata: Read-only
3. Subscribe to the **Pull request** event
4. Generate and download a private key
5. Note your App ID

### 2. Clone and configure

```bash
git clone https://github.com/yourusername/code-review-assistant
cd code-review-assistant
pip install -r requirements.txt
```

Create a `.env` file:

```
APP_ID=your_app_id
WEBHOOK_SECRET=your_webhook_secret
PRIVATE_KEY_PATH=private-key.pem
GROQ_API_KEY=your_groq_api_key
QDRANT_HOST=localhost
QDRANT_PORT=6333
```

Move your downloaded `.pem` file into the project root.

Get a free Groq API key at [console.groq.com](https://console.groq.com) — no credit card required.

### 3. Start all services

**Terminal 1 — Qdrant:**
```bash
docker run -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant
```

**Terminal 2 — FastAPI server:**
```bash
python -m uvicorn app.main:app --reload --port 8000
```

**Terminal 3 — ngrok:**
```bash
ngrok http 8000
```

Copy the ngrok URL and update your GitHub App's Webhook URL to:
```
https://xxxx.ngrok-free.app/webhook
```

**Terminal 4 — Evaluation dashboard:**
```bash
streamlit run dashboard.py
```
<img width="1884" height="767" alt="image" src="https://github.com/user-attachments/assets/59c00b10-d3eb-4f92-8759-a5b8002ee4d8" />

### 4. Install the app on a repo

In your GitHub App settings → **Install App** → select a repository.

### 5. Trigger the bot

Open or update a pull request on the installed repository. The bot will automatically post a review comment.

## Evaluation

The bot stores every generated review in a local SQLite database. The Streamlit dashboard at `http://localhost:8501` lets you:

- View all generated reviews
- Label each suggestion as "acted on" or "ignored"
- Track precision over time (% of suggestions that were actually useful)
- Monitor noise rate

Precision is defined as the fraction of suggestions that were acted on by the PR author. A suggestion is considered acted on if the author pushed a follow-up commit addressing it.

## How it works — key design decisions

**Why GitHub Apps instead of a Personal Access Token?**
GitHub Apps are a first-class bot identity with scoped permissions per installation. PATs are tied to a personal account and have no webhook support.

**Why two tokens (JWT + installation token)?**
The JWT proves identity (signed with your private key, valid 10 min). The installation token is scoped to a specific repo install (valid 1 hour). Short-lived tokens limit the blast radius of any credential leak.

**Why chunk by function/class instead of by line count?**
A function is a semantic unit. Line-based chunking splits functions in half and loses meaning. Function-level chunks mean each vector represents a complete, coherent piece of logic.

**Why deduplicate comments?**
A PR with 10 commits should not get 10 bot comments. The bot checks for an existing comment on each PR and edits it rather than creating a new one.

**Why exponential backoff on GitHub API calls?**
GitHub rate limits are per installation (5000 requests/hour). Backing off on 429/403 responses prevents cascading failures under load.
