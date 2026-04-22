import requests
import subprocess
import os
import shutil

def fetch_diff(diff_url: str, token: str) -> str:
    """
    Fetches the raw unified diff from GitHub.
    The diff_url comes directly from the PR payload.
    """
    resp = requests.get(diff_url, headers={
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3.diff",
    })
    resp.raise_for_status()
    return resp.text


def clone_repo(repo_full_name: str, token: str, target_dir: str) -> str:
    """
    Clones the repo so we can walk its files for import analysis.
    Uses the installation token for auth — works for private repos too.
    
    Returns the path to the cloned repo.
    """
    if os.path.exists(target_dir):
        shutil.rmtree(target_dir)  # fresh clone every time

    url = f"https://x-access-token:{token}@github.com/{repo_full_name}.git"
    subprocess.run(
        ["git", "clone", "--depth=1", url, target_dir],
        check=True,
        capture_output=True,
    )
    return target_dir