"""Minimal coding harness on the Claude Messages API (manual tool-use loop)."""
import os
import sys

import anthropic

from harness_common import TOOL_SPECS, execute_tool, gate_verdict

MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")
MAX_TURNS = 30
MAX_GATE_RETRIES = 3
FATAL_STOP_REASONS = {
    "refusal": "the model declined the request",
    "max_tokens": "response hit max_tokens",
}

TOOLS = [
    {"name": t["name"], "description": t["description"], "input_schema": t["parameters"], "strict": True}
    for t in TOOL_SPECS
]

SYSTEM = (
    "You are a coding agent working in one project directory. "
    "Read the relevant files before editing. Make one small change at a time. "
    "After each change, call run_checks and fix any failure before moving on. "
    "When the task is done, reply with a short summary of what changed and the last run_checks output."
)


def tool_results(content) -> list[dict]:
    results = []
    for block in content:
        if block.type == "tool_use":
            text, is_error = execute_tool(block.name, block.input)
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": text, "is_error": is_error})
    return results


def final_text(content) -> str:
    return next((b.text for b in content if b.type == "text"), "")


def run(task: str) -> int:
    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": task}]
    gate_retries = 0

    for _ in range(MAX_TURNS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=SYSTEM,
            tools=TOOLS,
            output_config={"effort": "high"},
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})
        reason = response.stop_reason

        if reason in FATAL_STOP_REASONS:
            print(f"stopped: {FATAL_STOP_REASONS[reason]}", file=sys.stderr)
            return 2
        if reason == "pause_turn":
            continue
        if reason == "tool_use":
            messages.append({"role": "user", "content": tool_results(response.content)})
            continue

        # end_turn: the model thinks it is done. The harness, not the model, decides.
        verdict, text = gate_verdict(gate_retries, MAX_GATE_RETRIES)
        if verdict == "pass":
            print(final_text(response.content))
            return 0
        if verdict == "fail":
            print(f"stopped: {text}", file=sys.stderr)
            return 1
        gate_retries += 1
        messages.append({"role": "user", "content": text})

    print(f"stopped: reached {MAX_TURNS} turns", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(run(" ".join(sys.argv[1:]) or "Make the failing tests pass."))
