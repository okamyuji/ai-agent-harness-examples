"""Fail unless every viable gremlins mutant was killed.

gremlins exited 0 in our checks even with live, timed-out, or zero mutants and a
--threshold-efficacy flag, so the gate reads the JSON report instead of the exit code.

Usage:
  gremlins unleash --workers 1 --timeout-coefficient 10 --diff origin/main -o gremlins.json ./internal
  python3 -I mutation_gate.py gremlins.json
"""
import json
import sys


def verdict(report: dict) -> tuple[bool, str]:
    total = report["mutants_total"]
    killed = report["mutants_killed"]
    viable = total - report["mutants_not_viable"]
    others = viable - killed - report["mutants_lived"] - report["mutants_not_covered"]
    summary = (
        f"total={total} killed={killed} lived={report['mutants_lived']} "
        f"not_covered={report['mutants_not_covered']} timed_out_or_other={others}"
    )
    if viable == 0:
        return False, f"no killed or live mutants: wrong path, empty --diff, or every mutant timed out ({summary})"
    return killed == viable, summary


def _self_test() -> None:
    base = {"mutants_total": 2, "mutants_killed": 2, "mutants_lived": 0, "mutants_not_viable": 0, "mutants_not_covered": 0}
    assert verdict(base)[0]
    assert not verdict({**base, "mutants_killed": 1, "mutants_lived": 1})[0]
    assert not verdict({**base, "mutants_killed": 0})[0]  # timed out
    assert not verdict({**base, "mutants_total": 0, "mutants_killed": 0})[0]
    assert not verdict({**base, "mutants_killed": 1, "mutants_not_covered": 1})[0]
    assert verdict({**base, "mutants_total": 3, "mutants_not_viable": 1})[0]


def main() -> int:
    if "--self-test" in sys.argv:
        _self_test()
        print("self-test ok")
        return 0
    with open(sys.argv[1], encoding="utf-8") as f:
        ok, summary = verdict(json.load(f))
    print(("PASS " if ok else "FAIL ") + summary)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
