# Fool setuptools to prevent
#     error: Namespace package problem: middlewared is a namespace package, but its
#     __init__.py does not call declare_namespace()! Please fix it.
#     (See the setuptools manual under "Namespace Packages" for details.)
# when running setup_test.py
# (it checks for presence of declare_namespace in __init__.py so the above paragraph
# alone does the job)

import os
import sys

from .fake_env import setup_fake_middleware_env

if os.environ.get("FAKE_ENV"):
    setup_fake_middleware_env()

_coverage = None


def _start_coverage():
    # Start coverage before `middlewared.main` imports the plugins, otherwise their module-level statements run
    # untraced. Keyed off `--coverage` in `argv` so the pytest subprocess `middlewared.main` spawns does not inherit it.
    global _coverage

    if not any(arg == "--coverage" or arg.startswith("--coverage=") for arg in sys.argv[1:]):
        return

    import argparse

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--coverage", nargs="?", const="middlewared", default=None)
    args, _ = parser.parse_known_args()

    try:
        import coverage
    except ImportError:
        raise SystemExit("--coverage requires the 'coverage' package to be installed")

    source = [pkg.strip() for pkg in args.coverage.split(",") if pkg.strip()]
    _coverage = coverage.Coverage(branch=True, source=source)
    _coverage.start()


_start_coverage()
