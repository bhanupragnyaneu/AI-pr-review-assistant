import tempfile
from app.auth import get_installation_token
from app.github_client import fetch_diff, clone_repo
from app.diff_parser import parse_diff, get_changed_files
from app.impact_analyzer import analyze_impact
from app.rag import index_repo, retrieve_relevant_chunks, generate_review

async def handle_pull_request(payload: dict):
    installation_id = payload["installation"]["id"]
    token = get_installation_token(installation_id)

    pr = payload["pull_request"]
    repo = payload["repository"]["full_name"]
    pr_number = pr["number"]
    diff_url = pr["diff_url"]
    pr_title = pr["title"]

    print(f"\n🔍 Analyzing PR #{pr_number} on {repo}: '{pr_title}'")

    # Phase 2: diff parsing + impact analysis
    raw_diff = fetch_diff(diff_url, token)
    hunks = parse_diff(raw_diff)
    changed_files = get_changed_files(hunks)
    print(f"   Changed files: {changed_files}")

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = clone_repo(repo, token, f"{tmpdir}/repo")
        impact = analyze_impact(changed_files, repo_path)
        print(f"   Impacted files: {impact.directly_impacted}")

        # Phase 3: index the repo + retrieve relevant chunks
        print(f"   Indexing repo...")
        index_repo(repo_path, repo)

    diff_summary = f"PR '{pr_title}' changes: {', '.join(changed_files)}"
    relevant_chunks = retrieve_relevant_chunks(
        changed_files=changed_files,
        diff_summary=diff_summary,
        repo_name=repo,
    )
    print(f"   Retrieved {len(relevant_chunks)} relevant chunks from vector DB")

    # Generate review
    print(f"   Generating review with LLM...")
    review = generate_review(
        pr_title=pr_title,
        changed_files=changed_files,
        impacted_files=impact.directly_impacted,
        diff_text=raw_diff,
        relevant_chunks=relevant_chunks,
    )

    print(f"\n📝 Review generated:")
    print(f"   Summary:   {review.get('summary')}")
    print(f"   Risks:     {review.get('risks')}")
    print(f"   Suggestions: {review.get('suggestions')}")
    print(f"   Tests:     {review.get('test_coverage')}")
    # print(f"\n✅ Phase 3 complete for PR #{pr_number}")

    # Phase 4 will post this as a GitHub comment