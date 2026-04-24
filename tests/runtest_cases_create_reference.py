#!/usr/bin/env python3
"""
Runs every case in runtest_cases.json under coverage and writes the result to
runtest_references/<case_name>/ (runtest.py does the write itself).

Must be executed from the tests/ directory, or from anywhere (cwd is adjusted).

Coverage notes
--------------
Lines that will always appear as *not covered* are genuine dead code in runtest.py:

  get_ipinfo  lines 213-228  – unreachable after early return on line 205
  get_random_vip lines 240-257 – unreachable after early return on line 238
  lines 233-234  – get_ipinfo always returns truthy values, so the guard never
                   triggers
  lines 394-423  – unreachable after sys.exit(0) on line 392

All other reachable lines are exercised by the 15 cases below.
"""

import glob
import json
import os
import shutil
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
        print(f"  created {key_pub}")

    license_file = os.path.join(HERE, "test_license.txt")
    with open(license_file, "w") as f:
        f.write("reference-license-content\n")


def run_case(case_name: str, args: list[str], extra_env: dict[str, str]) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["RUNTEST_TEST_NAME"] = case_name
    for key in HA_ENV_KEYS:
        env.pop(key, None)
    env.update(extra_env)

    cmd = [
        sys.executable, "-m", "coverage", "run",
        "--parallel-mode",
        "--include", os.path.join(HERE, "runtest.py"),
        os.path.join(HERE, "runtest.py"),
    ] + args

    return subprocess.run(cmd, env=env, cwd=HERE, capture_output=True, text=True)


def main() -> None:
    os.chdir(HERE)

    with open(os.path.join(HERE, "runtest_cases.json")) as f:
        cases: dict[str, dict] = json.load(f)

    print("Setting up prerequisites...")
    setup_prerequisites()

    # Remove stale coverage fragments from previous runs.
    for path in glob.glob(os.path.join(HERE, ".coverage.*")):
        os.unlink(path)
    coverage_file = os.path.join(HERE, ".coverage")
    if os.path.exists(coverage_file):
        os.unlink(coverage_file)

    failures: list[str] = []

    for case_name, case in cases.items():
        print(f"\nRunning {case_name!r} ...")

        result = run_case(case_name, case["cmd"], case.get("env", {}))

        if result.returncode != 0:
            print(f"  FAILED (exit {result.returncode})")
            if result.stderr.strip():
                for line in result.stderr.strip().splitlines()[-5:]:
                    print(f"    {line}")
            failures.append(case_name)
            continue

        ref_dir = os.path.join(HERE, "runtest_references", case_name)
        if os.path.isdir(ref_dir):
            print(f"  OK  -> {ref_dir}/")
        else:
            print(f"  ERROR: runtest_references/{case_name}/ was not created")
            failures.append(case_name)

    # ------------------------------------------------------------------ #
    # Coverage report                                                      #
    # ------------------------------------------------------------------ #
    print("\n" + "=" * 60)
    print("COVERAGE REPORT")
    print("=" * 60)

    subprocess.run(
        [sys.executable, "-m", "coverage", "combine"],
        cwd=HERE,
        check=True,
    )
    report = subprocess.run(
        [sys.executable, "-m", "coverage", "report",
         "--show-missing",
         "--include", "runtest.py"],
        cwd=HERE,
        capture_output=True,
        text=True,
    )
    print(report.stdout)
    if report.stderr.strip():
        print(report.stderr)

    subprocess.run(
        [sys.executable, "-m", "coverage", "html",
         "--include", "runtest.py",
         "-d", os.path.join(HERE, "coverage_html")],
        cwd=HERE,
    )
    print("HTML report written to tests/coverage_html/")

    # ------------------------------------------------------------------ #
    # Summary                                                              #
    # ------------------------------------------------------------------ #
    if failures:
        print(f"\nFailed cases ({len(failures)}): {failures}")
        sys.exit(1)
    else:
        print(f"\nAll {len(cases)} cases written to runtest_references/")


if __name__ == "__main__":
    main()
