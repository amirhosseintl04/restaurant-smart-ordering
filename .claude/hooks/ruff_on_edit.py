"""PostToolUse hook: format and lint an edited Python file with ruff.

Runs with ``python -I`` so it depends on the standard library only. It must never block
editing: when ruff is missing or anything unexpected happens it exits 0. When ruff reports
lint errors that ``--fix`` could not resolve, it exits 2 so Claude sees them as feedback.

Input: the PostToolUse JSON on stdin (``tool_input.file_path`` is absolute; on Windows it
uses backslashes). ``cwd`` follows the worktree the editing agent runs in.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def find_ruff(search_roots: list[Path]) -> list[str] | None:
    """Return a command prefix that runs ruff, or None when it is not available."""
    on_path = shutil.which("ruff")
    if on_path:
        return [on_path]
    for root in search_roots:
        for candidate in (
            root / ".venv" / "Scripts" / "ruff.exe",
            root / ".venv" / "bin" / "ruff",
        ):
            if candidate.is_file():
                return [str(candidate)]
    probe = subprocess.run(
        [sys.executable, "-m", "ruff", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode == 0:
        return [sys.executable, "-m", "ruff"]
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    file_path = (payload.get("tool_input") or {}).get("file_path")
    if not file_path:
        return 0
    target = Path(str(file_path).replace("\\", "/"))
    if target.suffix != ".py" or not target.is_file():
        return 0

    roots: list[Path] = []
    for key in ("cwd",):
        if payload.get(key):
            roots.append(Path(str(payload[key])))
    if os.environ.get("CLAUDE_PROJECT_DIR"):
        roots.append(Path(os.environ["CLAUDE_PROJECT_DIR"]))

    ruff = find_ruff(roots)
    if ruff is None:
        print("ruff_on_edit: ruff not found, skipping format and lint", file=sys.stderr)
        return 0

    workdir = str(roots[0]) if roots and roots[0].is_dir() else None
    subprocess.run(
        [*ruff, "format", str(target)],
        capture_output=True,
        text=True,
        check=False,
        cwd=workdir,
    )
    check = subprocess.run(
        [*ruff, "check", "--fix", str(target)],
        capture_output=True,
        text=True,
        check=False,
        cwd=workdir,
    )
    if check.returncode != 0:
        output = (check.stdout or "") + (check.stderr or "")
        print(f"ruff_on_edit: lint errors remain in {target}\n{output}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # never block editing because of the hook itself
        print(f"ruff_on_edit: skipped ({exc})", file=sys.stderr)
        sys.exit(0)
