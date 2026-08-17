"""Keep the integration suite's entitlement mocks spelling names the engine still knows.

`mock(..., args=[...])` only takes effect when the recorded arguments compare equal to the
ones the method is called with. A mock naming a feature that has since been renamed or
dropped therefore matches nothing, the real method runs, and the test carries on against
live system facts -- silently, and usually still green. Nothing in CI reads `tests/`, so
that rot is invisible until a suite starts failing for reasons that look unrelated.

This walks the integration suite as source text rather than importing it: those modules
need a live TrueNAS to import at all.
"""

import ast
import os

import pytest

from middlewared.utils.entitlements import POLICY

ENDPOINT = "truenas.entitlements.check"

# There is no precedent in this tree for locating the repo root from a unit test -- the alert
# AST scanners use get_middlewared_dir(), which resolves inside the installed package. That
# does not help here: `tests/` is a sibling of `src/`, not part of the package. So walk up
# from this file and skip when the result has no `tests/`, which is what happens under
# tests/run_unit_tests.py: it copies this tree into /usr/lib/python3/dist-packages and the
# walk-up lands in /usr/lib.
TESTS_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), *[os.pardir] * 5, "tests"))

pytestmark = pytest.mark.skipif(
    not os.path.isdir(TESTS_DIR),
    reason=f"integration suite not present at {TESTS_DIR} (running from an installed package)",
)

# Nine files carry a mock today and one names the endpoint through a plain call(). A scanner
# that stops matching would otherwise report an empty vocabulary and pass.
MINIMUM_SITES = 13


def _literal(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _feature_names():
    """Yield `(path, lineno, name)` for every site naming the entitlement endpoint.

    A `mock()` carries its feature in the `args` keyword; anything else -- today only a
    direct `call()` -- carries it as the next positional argument.
    """
    for dirpath, _, filenames in os.walk(TESTS_DIR):
        for filename in sorted(filenames):
            if not filename.endswith(".py"):
                continue
            path = os.path.join(dirpath, filename)
            with open(path, encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=path)

            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not node.args or _literal(node.args[0]) != ENDPOINT:
                    continue

                mocked = [kw.value for kw in node.keywords if kw.arg == "args"]
                if mocked:
                    yield path, node.lineno, mocked[0]
                elif len(node.args) > 1:
                    yield path, node.lineno, node.args[1]


def _sites():
    return list(_feature_names())


def test_the_scanner_finds_the_known_sites():
    assert len(_sites()) >= MINIMUM_SITES


def test_mocked_args_carry_exactly_one_feature():
    # `check` takes one argument, and main.py matches a mock on `args == list(params)`. A
    # list of any other length can never match, so the mock is inert and the real check runs.
    wrong = [
        (path, lineno, ast.unparse(node))
        for path, lineno, node in _sites()
        if isinstance(node, ast.List) and len(node.elts) != 1
    ]
    assert wrong == []


def test_mocked_features_are_in_the_live_policy():
    known = {str(key) for key in POLICY}
    unknown = []
    for path, lineno, node in _sites():
        elements = node.elts if isinstance(node, ast.List) else [node]
        for element in elements:
            name = _literal(element)
            # A non-literal is out of scope rather than a failure: this checks the vocabulary
            # spelled out in the suite, and a computed name is not spelled out.
            if name is not None and name not in known:
                unknown.append((os.path.relpath(path, TESTS_DIR), lineno, name))

    assert unknown == []
