"""Minimal coding harness on the OpenAI Responses API (manual function-calling loop)."""
import json
import os
import sys

from openai import OpenAI

from harness_common import TOOL_SPECS, execute_tool, gate_verdict

MODEL = os.environ.get("OPENAI_MODEL", "gpt-6-astra")
MAX_TURNS = 30
MAX_GATE_RETRIES = 3

TOOLS = [{"type": "function", "strict": True, **t} for t in TOOL_SPECS]

INSTRUCTIONS = (
    "You are a coding agent working in one project directory. "
    "Read the relevant files before editing. Make one small change at a time. "
    "After each change, call run_checks and fix any failure before moving on. "
    "When the task is done, reply with a short summary of what changed and the last run_checks output."
)


def call_outputs(output) -> list[dict]:
    results = []
    for item in output:
        if item.type == "function_call":
            text, _ = execute_tool(item.name, json.loads(item.arguments))
            results.append({"type": "function_call_output", "call_id": item.call_id, "output": text})
    return results


def run(task: str) -> int:
    client = OpenAI()
    input_list = [{"role": "user", "content": task}]
    gate_retries = 0

    for _ in range(MAX_TURNS):
        response = client.responses.create(model=MODEL, instructions=INSTRUCTIONS, tools=TOOLS, input=input_list)
        # Keep every output item, including reasoning items, so the next request sees the full history.
        input_list += response.output

        results = call_outputs(response.output)
        if results:
            input_list += results
            continue

        verdict, text = gate_verdict(gate_retries, MAX_GATE_RETRIES)
        if verdict == "pass":
            print(response.output_text)
            return 0
        if verdict == "fail":
            print(f"stopped: {text}", file=sys.stderr)
            return 1
        gate_retries += 1
        input_list.append({"role": "user", "content": text})

    print(f"stopped: reached {MAX_TURNS} turns", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(run(" ".join(sys.argv[1:]) or "Make the failing tests pass."))
