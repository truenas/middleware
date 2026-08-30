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

from middlewared.utils.entitlements import POLICY, DerivedEntitlement, LicenseFeature
from middlewared.utils.python import get_middlewared_dir

ENDPOINT = "truenas.entitlements.check"

VOCABULARIES = {"LicenseFeature": LicenseFeature, "DerivedEntitlement": DerivedEntitlement}

# The endpoint answers `NOT_GATED` for a key `POLICY` does not carry rather than raising, so a
# gate naming an unruled feature is silently open. Scanning the source is what replaces that
# runtime complaint, which means it has to see the gates: a scan that matches nothing passes.
MINIMUM_GATES = 25

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


def _dotted(node):
    """Render an attribute chain as its dotted source text, or None if it is not one."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    return ".".join(reversed(parts))


def _names_the_endpoint(call):
    """Whether `call` hands the endpoint to something, by bound method or by name.

    A gate reaches it as `<something>.truenas.entitlements.check` passed to `call2`, and
    `plugins/etc.py` reaches it as a `method=` string on a `CtxMethod`.
    """
    for value in [*call.args, *(keyword.value for keyword in call.keywords)]:
        if _literal(value) == ENDPOINT or (_dotted(value) or "").endswith(ENDPOINT):
            return True
    return False


def test_production_gates_name_a_feature_the_live_policy_rules_on():
    """Every feature a gate spells out has to have a rule, or the gate is permanently open."""
    known = {str(key) for key in POLICY}
    gates = 0
    unruled = []
    source_dir = get_middlewared_dir()
    for dirpath, dirnames, filenames in os.walk(source_dir):
        # This package holds the tests themselves, several of which name unruled features on
        # purpose to pin what the endpoint answers for one.
        dirnames[:] = [name for name in dirnames if name != "pytest"]
        for filename in sorted(filenames):
            if not filename.endswith(".py"):
                continue
            path = os.path.join(dirpath, filename)
            with open(path, encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=path)

            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not _names_the_endpoint(node):
                    continue

                gates += 1
                for inner in ast.walk(node):
                    if not isinstance(inner, ast.Attribute) or not isinstance(inner.value, ast.Name):
                        continue
                    vocabulary = VOCABULARIES.get(inner.value.id)
                    if vocabulary is None:
                        continue
                    member = vocabulary.__members__.get(inner.attr)
                    if member is None or str(member) not in known:
                        location = (os.path.relpath(path, source_dir), node.lineno)
                        unruled.append((*location, f"{inner.value.id}.{inner.attr}"))

    assert unruled == []
    assert gates >= MINIMUM_GATES
