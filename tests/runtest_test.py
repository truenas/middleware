#!/usr/bin/env python3
"""
Runs every case in runtest_cases.json, writes results to runtest_results/,
then compares with runtest_references/ and prints any differences.
"""

from difflib import unified_diff
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

HA_ENV_KEYS = (
    "virtual_ip", "domain", "hostname_virtual", "hostname",
    "hostname_b", "primary_dns", "secondary_dns",
    "controller1_ip", "controller2_ip",
)


def setup_prerequisites() -> None:
    ssh_dir = os.path.expanduser("~/.ssh")
    key_pub = os.path.join(ssh_dir, "test_id_rsa.pub")
    if not os.path.exists(key_pub):
        os.makedirs(ssh_dir, exist_ok=True)
        with open(key_pub, "w") as f:
            f.write("ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC test@reference\n")

    license_file = os.path.join(HERE, "test_license.txt")
    if not os.path.exists(license_file):
        with open(license_file, "w") as f:
            f.write("reference-license-content\n")


def run_case(case_name: str, args: list[str], extra_env: dict[str, str]) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["RUNTEST_TEST_NAME"] = case_name
    env["RUNTEST_OUTPUT_DIR"] = "runtest_results"
    for key in HA_ENV_KEYS:
        env.pop(key, None)
    env.update(extra_env)

    cmd = [sys.executable, os.path.join(HERE, "runtest.py")] + args
    return subprocess.run(cmd, env=env, cwd=HERE, capture_output=True, text=True)


def diff_json(ref: dict, actual: dict, path: str = "") -> list[str]:
    diffs = []
    for key in ref:
        full = f"{path}.{key}" if path else key
        if key not in actual:
            diffs.append(f"  missing key {full!r}")
        elif isinstance(ref[key], dict) and isinstance(actual[key], dict):
            diffs.extend(diff_json(ref[key], actual[key], full))
        elif ref[key] != actual[key]:
            diffs.append(f"  {full!r}:")
            diffs.append(f"    expected: {ref[key]!r}")
            diffs.append(f"    actual:   {actual[key]!r}")
    for key in actual:
        if key not in ref:
            full = f"{path}.{key}" if path else key
            diffs.append(f"  extra key {full!r}: {actual[key]!r}")
    return diffs


def compare_case(case_name: str) -> list[str]:
    ref_dir = os.path.join(HERE, "runtest_references", case_name)
    actual_dir = os.path.join(HERE, "runtest_results", case_name)
    diffs = []

    for filename in ("result", "auto_config.py"):
        ref_path = os.path.join(ref_dir, filename)
        actual_path = os.path.join(actual_dir, filename)

        if not os.path.exists(ref_path):
            diffs.append(f"  reference {filename!r} not found")
            continue
        if not os.path.exists(actual_path):
            diffs.append(f"  result {filename!r} not found")
            continue

        if filename == "result":
            with open(ref_path) as f:
                ref = json.load(f)
            with open(actual_path) as f:
                actual = json.load(f)
            diffs.extend(diff_json(ref, actual))
        else:
            with open(ref_path) as f:
                ref_text = f.read()
            with open(actual_path) as f:
                actual_text = f.read()
            if ref_text != actual_text:
                diffs.append(f"  {filename!r} differs")
                print("\n".join(unified_diff(ref_text.split("\n"), actual_text.split("\n"))))

    return diffs


def main() -> None:
    os.chdir(HERE)

    with open(os.path.join(HERE, "runtest_cases.json")) as f:
        cases: dict[str, dict] = json.load(f)

    setup_prerequisites()
    os.makedirs(os.path.join(HERE, "runtest_results"), exist_ok=True)

    run_failures: list[str] = []

    print("Running test cases...")
    for case_name, case in cases.items():
        print(f"  {case_name} ...", end=" ", flush=True)
        result = run_case(case_name, case["cmd"], case.get("env", {}))
        if result.returncode != 0:
            print(f"FAILED (exit {result.returncode})")
            for line in result.stderr.strip().splitlines()[-3:]:
                print(f"    {line}")
            run_failures.append(case_name)
        else:
            print("OK")

    print()
    print("Comparing results with references...")
    diff_failures: list[str] = []

    for case_name in cases.keys():
        if case_name in run_failures:
            print(f"  {case_name}: SKIPPED (run failed)")
            continue
        diffs = compare_case(case_name)
        if diffs:
            print(f"\n  {case_name}: DIFFERS")
            for line in diffs:
                print(line)
            diff_failures.append(case_name)
        else:
            print(f"  {case_name}: OK")

    print()
    if run_failures:
        print(f"Run failures ({len(run_failures)}): {run_failures}")
    if diff_failures:
        print(f"Diff failures ({len(diff_failures)}): {diff_failures}")
    if run_failures or diff_failures:
        sys.exit(1)
    else:
        print(f"All {len(cases)} cases passed.")


if __name__ == "__main__":
    main()
