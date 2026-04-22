import re
from dataclasses import dataclass

@dataclass
class Hunk:
    filename: str
    added_lines: list[str]
    removed_lines: list[str]
    line_start: int
    line_count: int

def parse_diff(raw_diff: str) -> list[Hunk]:
    """
    Turns a unified diff string into a list of Hunks.
    
    A unified diff looks like:
    
    diff --git a/app/auth.py b/app/auth.py
    --- a/app/auth.py
    +++ b/app/auth.py
    @@ -10,6 +10,8 @@
    -old line
    +new line
     context line
    """
    hunks = []
    current_file = None
    current_hunk = None

    for line in raw_diff.splitlines():
        # New file being diffed
        if line.startswith("+++ b/"):
            current_file = line[6:]  # strips "+++ b/"

        # New hunk header: @@ -old_start,old_count +new_start,new_count @@
        elif line.startswith("@@") and current_file:
            match = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if match:
                if current_hunk:
                    hunks.append(current_hunk)
                current_hunk = Hunk(
                    filename=current_file,
                    added_lines=[],
                    removed_lines=[],
                    line_start=int(match.group(1)),
                    line_count=int(match.group(2) or 1),
                )

        elif current_hunk:
            if line.startswith("+") and not line.startswith("+++"):
                current_hunk.added_lines.append(line[1:])
            elif line.startswith("-") and not line.startswith("---"):
                current_hunk.removed_lines.append(line[1:])

    if current_hunk:
        hunks.append(current_hunk)

    return hunks


def get_changed_files(hunks: list[Hunk]) -> list[str]:
    """Returns unique list of files that have changes."""
    return list({h.filename for h in hunks})