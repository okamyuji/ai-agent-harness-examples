"""Offline tests for the sample harnesses. Fake SDK clients replace the real APIs.

Run: python3 -m unittest test_harness.py
"""
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest import mock

# The real SDKs are not needed: register stub modules before importing the harnesses.
for _name, _attr in (("anthropic", "Anthropic"), ("openai", "OpenAI")):
    _stub = sys.modules.setdefault(_name, types.ModuleType(_name))
    if not hasattr(_stub, _attr):
        setattr(_stub, _attr, None)
_workdir = tempfile.mkdtemp()
os.environ["HARNESS_WORKDIR"] = _workdir
Path(_workdir, "app.py").write_text("print('hi')\n", encoding="utf-8")

import claude_harness  # noqa: E402
import harness_common  # noqa: E402
import openai_harness  # noqa: E402


class FakeAPI:
    """Returns scripted responses in order and records every request."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return self.responses.pop(0)


def claude_client(responses):
    api = FakeAPI(responses)
    return api, NS(messages=api)


def openai_client(responses):
    api = FakeAPI(responses)
    return api, NS(responses=api)


def tool_use(name, args, block_id="tu_1"):
    return NS(stop_reason="tool_use", content=[NS(type="tool_use", name=name, input=args, id=block_id)])


def end_turn(text):
    return NS(stop_reason="end_turn", content=[NS(type="text", text=text)])


class ClaudeHarnessTest(unittest.TestCase):
    def run_with(self, responses, gate_results):
        api, client = claude_client(responses)
        with mock.patch.object(claude_harness.anthropic, "Anthropic", lambda: client, create=True), mock.patch.object(
            harness_common, "run_checks", side_effect=gate_results
        ):
            code = claude_harness.run("fix it")
        return code, api

    def test_tool_call_then_gate_retry_then_pass(self):
        code, api = self.run_with(
            [tool_use("read_file", {"path": "app.py"}), end_turn("first"), end_turn("done")],
            [(False, "exit=1\nFAILED"), (True, "exit=0")],
        )
        self.assertEqual(code, 0)
        tool_result = api.requests[1]["messages"][2]["content"][0]
        self.assertEqual(tool_result["tool_use_id"], "tu_1")
        self.assertFalse(tool_result["is_error"])
        self.assertIn("print('hi')", tool_result["content"])
        # The harness appends to one list, so the last request holds the whole history.
        history = api.requests[-1]["messages"]
        gate_notes = [m["content"] for m in history if m["role"] == "user" and isinstance(m["content"], str)]
        self.assertTrue(any("quality gate failed" in note for note in gate_notes), gate_notes)

    def test_guardrail_block_is_returned_as_error_result(self):
        code, api = self.run_with(
            [tool_use("read_file", {"path": "../secret"}), end_turn("done")], [(True, "exit=0")]
        )
        self.assertEqual(code, 0)
        result = api.requests[1]["messages"][2]["content"][0]
        self.assertTrue(result["is_error"])
        self.assertIn("blocked by guardrail", result["content"])

    def test_stops_after_gate_retry_limit(self):
        responses = [end_turn(f"try {i}") for i in range(claude_harness.MAX_GATE_RETRIES + 1)]
        code, _ = self.run_with(responses, [(False, "exit=1")] * len(responses))
        self.assertEqual(code, 1)

    def test_refusal_stops_with_code_2(self):
        code, _ = self.run_with([NS(stop_reason="refusal", content=[])], [])
        self.assertEqual(code, 2)


class OpenAIHarnessTest(unittest.TestCase):
    def test_function_call_then_gate_retry_then_pass(self):
        call = NS(type="function_call", name="read_file", arguments=json.dumps({"path": "app.py"}), call_id="c1")
        responses = [
            NS(output=[call], output_text=""),
            NS(output=[NS(type="message")], output_text="first"),
            NS(output=[NS(type="message")], output_text="done"),
        ]
        api, client = openai_client(responses)
        with mock.patch.object(openai_harness, "OpenAI", lambda: client), mock.patch.object(
            harness_common, "run_checks", side_effect=[(False, "exit=1"), (True, "exit=0")]
        ):
            code = openai_harness.run("fix it")
        self.assertEqual(code, 0)
        outputs = [i for i in api.requests[1]["input"] if isinstance(i, dict) and i.get("type") == "function_call_output"]
        self.assertEqual(outputs[0]["call_id"], "c1")
        self.assertIn("print('hi')", outputs[0]["output"])


class GuardrailTest(unittest.TestCase):
    def test_env_files_are_blocked_regardless_of_case_or_suffix(self):
        for name in (".ENV", ".env.production", "ID_RSA"):
            text, is_error = harness_common.execute_tool("read_file", {"path": name})
            self.assertTrue(is_error, name)
            self.assertIn("not allowed", text, name)

    def test_git_directory_is_blocked_regardless_of_case(self):
        for path in (".git/hooks/pre-commit", ".GIT/hooks/pre-commit"):
            text, is_error = harness_common.execute_tool("write_file", {"path": path, "content": "x"})
            self.assertTrue(is_error, path)
            self.assertIn("not allowed", text, path)

    def test_bad_arguments_return_errors_instead_of_crashing(self):
        for args in ({"path": "a\x00b"}, {"path": 5}):
            _, is_error = harness_common.execute_tool("read_file", args)
            self.assertTrue(is_error, args)

    def test_approval_prompt_shows_the_content(self):
        with mock.patch("builtins.input", return_value="n") as fake_input:
            harness_common.execute_tool("write_file", {"path": "x.py", "content": "import os"})
        self.assertIn("import os", fake_input.call_args.args[0])


class ApprovalTest(unittest.TestCase):
    def test_write_without_terminal_is_declined_not_crashed(self):
        with mock.patch("builtins.input", side_effect=EOFError):
            text, is_error = harness_common.execute_tool("write_file", {"path": "new.txt", "content": "x"})
        self.assertTrue(is_error)
        self.assertIn("declined", text)
        self.assertFalse(Path(_workdir, "new.txt").exists())


class RunChecksTest(unittest.TestCase):
    def test_missing_command_fails_without_raising(self):
        with mock.patch.object(harness_common, "CHECK_CMD", "no-such-command-xyz"):
            ok, out = harness_common.run_checks()
        self.assertFalse(ok)
        self.assertIn("not found", out)


if __name__ == "__main__":
    unittest.main()
