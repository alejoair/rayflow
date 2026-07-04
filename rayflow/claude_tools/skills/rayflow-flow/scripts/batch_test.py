#!/usr/bin/env python3
"""Runs a flow against MANY test cases in one shot, against a running
`rayflow serve`'s REST API (POST /editor/flows/{name}/test — the same
endpoint the MCP `test_flow` tool calls) — instead of one MCP round-trip
per case. Use this once you have more than a couple of input/expected
pairs to check (edge cases, regressions).

Cases file (JSON): a list of objects, each:
    {"name": "optional label", "inputs": {...}, "expected_outputs": {...}}
`name` is optional (falls back to the case's index). `expected_outputs` is
optional too (omit it to just see actual outputs for exploration).

Usage:
    python3 .claude/skills/rayflow-flow/scripts/batch_test.py my_flow cases.json
    python3 .../batch_test.py my_flow cases.json --url http://localhost:8000

Requires `rayflow serve` already running (this hits its HTTP API — it does
NOT import rayflow directly, so no need to run it from the project root).
Exit code 0 if every case passed, 1 otherwise (including on a connection
or HTTP error reaching the server).
"""
import argparse
import json
import sys
import urllib.error
import urllib.request


def run_case(url: str, flow_name: str, case: dict) -> dict:
    body = {"inputs": case.get("inputs", {})}
    if "expected_outputs" in case:
        body["expected_outputs"] = case["expected_outputs"]
    req = urllib.request.Request(
        f"{url}/editor/flows/{flow_name}/test",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("flow_name")
    parser.add_argument("cases_file")
    parser.add_argument("--url", default="http://localhost:8000",
                         help="Base URL of the running rayflow serve (default: %(default)s)")
    args = parser.parse_args()

    try:
        with open(args.cases_file, encoding="utf-8") as f:
            cases = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"error reading '{args.cases_file}': {e}", file=sys.stderr)
        return 1
    if not isinstance(cases, list):
        print("cases file must be a JSON list of {name?, inputs, expected_outputs?}", file=sys.stderr)
        return 1

    all_passed = True
    for i, case in enumerate(cases):
        label = case.get("name", f"case {i}")
        try:
            result = run_case(args.url, args.flow_name, case)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")
            print(f"[ERROR] {label}: HTTP {e.code} — {detail}")
            all_passed = False
            continue
        except urllib.error.URLError as e:
            print(f"[ERROR] {label}: could not reach {args.url} ({e.reason}) — "
                  f"is 'rayflow serve' running?")
            all_passed = False
            continue

        if result.get("error") is not None:
            print(f"[FAIL]  {label}: flow errored — {result['error']}")
            all_passed = False
            continue

        passed = result.get("passed")
        if passed is False:
            print(f"[FAIL]  {label}: mismatches={result.get('mismatches')}")
            all_passed = False
        elif passed is True:
            print(f"[PASS]  {label}")
        else:
            print(f"[INFO]  {label}: no expected_outputs given — actual={result.get('actual')}")

    print(f"\n{'ALL PASSED' if all_passed else 'SOME FAILED'} ({len(cases)} case(s))")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
