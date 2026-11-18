"""Tools the agent can use to look at the files in sample_app/.

The agent can only see files inside SAMPLE_FOLDER. It cannot read
anything outside it (for example ../.env, which holds the API key).
"""
from pathlib import Path

SAMPLE_FOLDER = Path("sample_app")
MAX_LINES = 80    # the most lines returned in one call
MAX_CHARS = 6000  # the most characters returned in one call


def list_files() -> dict:
    """List the files the agent is allowed to read."""
    files = sorted(p.name for p in SAMPLE_FOLDER.glob("*.py"))
    return {"files": files}


def read_file(path: str, start_line: int = 1, end_line: int = 80) -> dict:
    """Read lines from one file in sample_app, with line numbers.

    Use a file name from list_files, for example "app.py".
    Returns at most 80 lines and 6000 characters per call.
    """
    allowed = list_files()["files"]
    if path not in allowed:
        return {"error": f"Cannot read '{path}'. Use a file name from list_files: {', '.join(allowed)}"}

    lines = (SAMPLE_FOLDER / path).read_text(encoding="utf-8").splitlines()
    if start_line < 1 or start_line > len(lines) or end_line < start_line:
        return {"error": f"Bad line range. {path} has {len(lines)} lines; use 1 to {len(lines)}."}

    end = min(end_line, start_line + MAX_LINES - 1, len(lines))
    content = "\n".join(f"{n}: {lines[n - 1]}" for n in range(start_line, end + 1))
    return {
        "path": path,
        "content": content[:MAX_CHARS],
        "total_lines": len(lines),
        "truncated": end < min(end_line, len(lines)) or len(content) > MAX_CHARS,
    }