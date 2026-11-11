"""Per-function CRAP for Go: joins `gocyclo -over 0` with `go tool cover -func`, fails above a threshold.

Usage:
  gocyclo -over 0 . > cyclo.txt
  go test -coverprofile=cover.out ./... && go tool cover -func=cover.out > cover.txt
  python3 -I crap.py cyclo.txt cover.txt [--max 15]
"""
import argparse
import re
import sys

CYCLO_LINE = re.compile(r"^(\d+)\s+\S+\s+(\S+)\s+(\S+?):(\d+):\d+$")
COVER_LINE = re.compile(r"^(\S+?):(\d+):\s+(\S+)\s+([\d.]+)%$")


def crap(complexity: int, coverage_pct: float) -> float:
    return complexity**2 * (1 - coverage_pct / 100) ** 3 + complexity


def parse_cover(lines) -> dict[tuple[str, int], float]:
    result = {}
    for line in lines:
        m = COVER_LINE.match(line.strip())
        if m:
            result[(m.group(1), int(m.group(2)))] = float(m.group(4))
    return result


def find_coverage(cover: dict, rel_path: str, line: int) -> float:
    # cover -func prints module import paths; gocyclo prints paths relative to the scan root.
    for (path, ln), pct in cover.items():
        if ln == line and (path == rel_path or path.endswith("/" + rel_path.removeprefix("./"))):
            return pct
    return 0.0


def report(cyclo_lines, cover_lines, max_crap: float) -> list[str]:
    cover = parse_cover(cover_lines)
    failures = []
    for line in cyclo_lines:
        m = CYCLO_LINE.match(line.strip())
        if not m:
            continue
        cc, func, path, ln = int(m.group(1)), m.group(2), m.group(3), int(m.group(4))
        score = crap(cc, find_coverage(cover, path, ln))
        if score > max_crap:
            failures.append(f"{path}:{ln} {func} CRAP={score:.1f} (complexity={cc})")
    return failures


def _self_test() -> None:
    assert crap(1, 100) == 1
    assert crap(10, 0) == 110
    assert abs(crap(5, 50) - 8.125) < 1e-9
    cyclo = ["4 slug Make slug.go:9:1", "1 slug Tiny other.go:3:1"]
    cover = ["example.com/slug/slug.go:9:\tMake\t100.0%", "total:\t(statements)\t100.0%"]
    assert report(cyclo, cover, 15) == []
    assert report(cyclo, cover, 0.5) == ["slug.go:9 Make CRAP=4.0 (complexity=4)", "other.go:3 Tiny CRAP=2.0 (complexity=1)"]


def main() -> int:
    if "--self-test" in sys.argv:
        _self_test()
        print("self-test ok")
        return 0
    ap = argparse.ArgumentParser()
    ap.add_argument("cyclo")
    ap.add_argument("cover")
    ap.add_argument("--max", type=float, default=15)
    args = ap.parse_args()
    with open(args.cyclo, encoding="utf-8") as c, open(args.cover, encoding="utf-8") as v:
        failures = report(c.readlines(), v.readlines(), args.max)
    for f in failures:
        print(f)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
