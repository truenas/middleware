"""Keep every production entitlement gate spelling a feature the live policy rules on.

The endpoint answers `NOT_GATED` for a key `POLICY` does not carry rather than raising, so a
gate naming an unruled feature is silently open -- it denies nothing and says nothing. There
is no runtime complaint to notice, which is what this scan replaces.

It reads the source rather than importing it, because reaching a gate at runtime means
standing up the plugin that holds it. A scan that matches nothing would pass, so the number
of gates found is asserted too.
"""

import ast
import os

from middlewared.utils.entitlements import POLICY, DerivedEntitlement, LicenseFeature
from middlewared.utils.python import get_middlewared_dir

ENDPOINT = "truenas.entitlements.check"

VOCABULARIES = {"LicenseFeature": LicenseFeature, "DerivedEntitlement": DerivedEntitlement}

MINIMUM_GATES = 25


def _literal(node):
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


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
