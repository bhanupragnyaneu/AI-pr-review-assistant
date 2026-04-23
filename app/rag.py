import os
import uuid
import json
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue
)
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
from app.chunker import chunk_repo
from qdrant_client.models import SearchRequest

load_dotenv()

# --- clients ---
# Groq uses an OpenAI-compatible API — same interface, different backend
groq_client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

# Local embedding model — runs on your machine, no API calls, no cost
# Downloads ~90MB on first run, then cached locally forever
embed_model = SentenceTransformer("all-MiniLM-L6-v2")

qdrant = QdrantClient(
    host=os.getenv("QDRANT_HOST", "localhost"),
    port=int(os.getenv("QDRANT_PORT", 6333))
)

COLLECTION = "code_chunks"
EMBED_DIM = 384  # dimension of all-MiniLM-L6-v2 vectors


def ensure_collection():
    """
    Creates the Qdrant collection if it doesn't exist.
    EMBED_DIM must match the embedding model's output size.
    all-MiniLM-L6-v2 outputs 384-dimensional vectors.
    """
    existing = [c.name for c in qdrant.get_collections().collections]
    if COLLECTION not in existing:
        qdrant.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(
                size=EMBED_DIM,
                distance=Distance.COSINE
            ),
        )
        print(f"✅ Created Qdrant collection: {COLLECTION}")


def embed(text: str) -> list[float]:
    """
    Converts text to a vector using a local sentence-transformers model.
    Runs entirely on your CPU — no internet, no API, no cost.
    Similar code will produce similar vectors (close in vector space).
    """
    vector = embed_model.encode(text, show_progress_bar=False)
    return vector.tolist()


def index_repo(repo_path: str, repo_name: str):
    """
    Indexes every function/class in the repo into Qdrant.
    Safe to call multiple times — upsert won't create duplicates
    if you use stable IDs. Here we use uuid for simplicity
    since this runs fresh per PR.
    """
    ensure_collection()
    chunks = chunk_repo(repo_path)
    print(f"📚 Indexing {len(chunks)} chunks from {repo_name}...")

    if not chunks:
        print("   No Python files found to index — skipping")
        return

    points = []
    for chunk in chunks:
        text_to_embed = f"# {chunk.filepath} - {chunk.name}\n{chunk.source}"
        vector = embed(text_to_embed)

        points.append(PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload={
                "repo": repo_name,
                "filepath": chunk.filepath,
                "chunk_type": chunk.chunk_type,
                "name": chunk.name,
                "source": chunk.source,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
            }
        ))

    # Upload in batches of 100
    batch_size = 100
    for i in range(0, len(points), batch_size):
        batch = points[i:i + batch_size]
        qdrant.upsert(collection_name=COLLECTION, points=batch)
        print(f"   Uploaded {min(i + batch_size, len(points))}/{len(points)} chunks")

    print(f"✅ Indexing complete for {repo_name}")


def retrieve_relevant_chunks(
    changed_files: list[str],
    diff_summary: str,
    repo_name: str,
    top_k: int = 5) -> list[dict]:
    """
    Finds the most semantically similar code chunks to the diff.
    Returns empty list gracefully if collection is empty.
    """
    ensure_collection()

    # Check if collection has any points before searching
    count = qdrant.count(collection_name=COLLECTION).count
    if count == 0:
        print("   Vector DB is empty — skipping retrieval")
        return []

    query_vector = embed(diff_summary)


    results = qdrant.query_points(
        collection_name=COLLECTION,
        query=query_vector,
        query_filter=Filter(
            must=[FieldCondition(
                key="repo",
                match=MatchValue(value=repo_name)
            )]
        ),
        limit=top_k,
        with_payload=True,).points

    return [hit.payload for hit in results]


def generate_review(
    pr_title: str,
    changed_files: list[str],
    impacted_files: list[str],
    diff_text: str,
    relevant_chunks: list[dict],
) -> dict:
    """
    Sends the PR context to Groq's LLM and gets back a structured review.
    Uses llama3-8b — free, fast, runs on Groq's servers.
    Low temperature (0.2) keeps output consistent and structured.
    """
    chunk_context = "\n\n".join([
        f"### {c['filepath']} - {c['name']}\n```python\n{c['source']}\n```"
        for c in relevant_chunks
    ]) if relevant_chunks else "No similar code found in codebase."

    system_prompt = """You are a senior software engineer doing a code review.
You will be given a PR diff, impacted files, and relevant codebase context.
Respond ONLY with a valid JSON object in this exact format, no markdown, no explanation outside the JSON:
{
  "summary": "one sentence describing what this PR does",
  "risks": ["risk 1", "risk 2"],
  "suggestions": ["specific actionable suggestion 1", "specific suggestion 2"],
  "test_coverage": "one sentence about whether test coverage looks adequate"
}"""

    user_prompt = f"""PR Title: {pr_title}

Changed files: {', '.join(changed_files)}
Impacted files (import dependents): {', '.join(impacted_files) or 'none detected'}

Diff:
{diff_text[:3000]}

Relevant codebase context:
{chunk_context[:2000]}"""

    response = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )

    raw = response.choices[0].message.content

    # Strip markdown code fences if LLM wraps response in them
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        # Graceful fallback — never crash on bad LLM output
        print(f"   ⚠️ Could not parse LLM JSON, returning raw")
        return {
            "summary": raw[:200],
            "risks": [],
            "suggestions": [],
            "test_coverage": "Could not parse structured output"
        }