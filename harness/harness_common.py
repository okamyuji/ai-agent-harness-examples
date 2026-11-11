"""Provider-neutral parts of the sample harness: tools, guardrails, and the quality gate."""
import os
import shlex
import subprocess
import sys
from pathlib import Path

WORKDIR = Path(os.environ.get("HARNESS_WORKDIR", ".")).resolve()
CHECK_CMD = os.environ.get("HARNESS_CHECK_CMD", "pytest -q")
DENY_NAMES = {"id_rsa", "id_ed25519"}
PREVIEW_CHARS = 500
MAX_OUTPUT_CHARS = 4000

TOOL_SPECS = [
    {
        "name": "read_file",
        "description": (
            "Read a UTF-8 text file inside the project. "
            "Use a path relative to the project root. Returns at most 4000 characters."
        ),
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Relative path, e.g. src/app.py"}},
            "required": ["path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "write_file",
        "description": (
            "Overwrite a text file inside the project with the full new content. "
            "A human approves every write before it runs."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path, e.g. src/app.py"},
                "content": {"type": "string", "description": "Complete new file content"},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
    },
    {
        "name": "run_checks",
        "description": (
            "Run the project's test command and return the exit code and the last lines of output. "
            "Call this after every change."
        ),
        "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
    },
]


class GuardrailError(Exception):
    """Raised when a tool call crosses a boundary. The message goes back to the model."""


def resolve_inside_workdir(relative: str) -> Path:
    target = (WORKDIR / relative).resolve()
    if not target.is_relative_to(WORKDIR):
        raise GuardrailError(f"path '{relative}' is outside the project root; use a path under it")
    # Compare lowercased names: macOS file systems are case-insensitive by default.
    name = target.name.lower()
    parts = {p.lower() for p in target.relative_to(WORKDIR).parts}
    if name.startswith(".env") or name in DENY_NAMES or ".git" in parts:
        raise GuardrailError(f"reading or writing '{relative}' is not allowed")
    return target


def ask_approval(summary: str) -> bool:
    try:
        answer = input(f"\n[approval] {summary}\nAllow? [y/N] ")
    except EOFError:  # no terminal (CI, piped stdin): treat as "not approved"
        return False
    return answer.strip().lower() == "y"


def read_file(path: str) -> str:
    text = resolve_inside_workdir(path).read_text(encoding="utf-8")
    if len(text) > MAX_OUTPUT_CHARS:
        return text[:MAX_OUTPUT_CHARS] + f"\n[truncated: {len(text)} chars total; ask for a smaller file]"
    return text


def write_file(path: str, content: str) -> str:
    target = resolve_inside_workdir(path)
    preview = content[:PREVIEW_CHARS] + ("\n[...]" if len(content) > PREVIEW_CHARS else "")
    if not ask_approval(f"write {len(content)} chars to {path}:\n{preview}"):
        raise GuardrailError("the human declined this write; propose a different change or stop")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"wrote {path}"


def run_checks() -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            shlex.split(CHECK_CMD), cwd=WORKDIR, capture_output=True, text=True, timeout=600, check=False
        )
    except FileNotFoundError as e:
        return False, f"check command not found: {e}"
    except subprocess.TimeoutExpired:
        return False, "check command timed out after 600s"
    tail = (proc.stdout + proc.stderr)[-MAX_OUTPUT_CHARS:]
    return proc.returncode == 0, f"exit={proc.returncode}\n{tail}"


def gate_verdict(retries_used: int, max_retries: int) -> tuple[str, str]:
    """Quality gate run by the harness when the model says it is done: ("pass" | "retry" | "fail", text)."""
    ok, output = run_checks()
    if ok:
        return "pass", output
    if retries_used >= max_retries:
        return "fail", f"quality gate still failing after {max_retries} retries\n{output}"
    return "retry", f"The quality gate failed. Fix it before finishing.\n{output}"


def execute_tool(name: str, args: dict) -> tuple[str, bool]:
    """Returns (result text, is_error). Errors are returned to the model, not raised."""
    try:
        if name == "read_file":
            return read_file(args["path"]), False
        if name == "write_file":
            return write_file(args["path"], args["content"]), False
        if name == "run_checks":
            ok, output = run_checks()
            return output, not ok
        return f"unknown tool '{name}'", True
    except GuardrailError as e:
        return f"blocked by guardrail: {e}", True
    except (OSError, ValueError, TypeError, KeyError) as e:  # ValueError covers UnicodeDecodeError and NUL bytes
        return f"{type(e).__name__}: {e}", True


def _self_test() -> None:
    assert resolve_inside_workdir("src/app.py") == WORKDIR / "src" / "app.py"
    for bad in ("../outside.txt", "/etc/passwd", ".env", "sub/.env"):
        try:
            resolve_inside_workdir(bad)
        except GuardrailError:
            continue
        raise AssertionError(f"guardrail let '{bad}' through")
    text, is_error = execute_tool("read_file", {"path": "../x"})
    assert is_error and text.startswith("blocked by guardrail"), text
    text, is_error = execute_tool("no_such_tool", {})
    assert is_error, text
    print("self-test ok")


if __name__ == "__main__" and "--self-test" in sys.argv:
    _self_test()
