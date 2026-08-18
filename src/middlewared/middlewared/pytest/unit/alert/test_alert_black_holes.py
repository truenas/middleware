"""No alert may be created where its own class does not apply.

A source and the classes it creates carry independent rules. Where the source's rule is
satisfied and a class's is not, the source runs, the alert is created, persisted and then
denied at every point it would be shown -- a black hole that reports nothing at runtime and
that no other test in this tree can see, because each declaration is individually consistent.

The source-to-class relation is inferred from the syntax and deliberately over-approximates:
every ``*AlertClass`` name appearing anywhere in a source's body is an edge, reachable or not.
Over-approximating is the safe direction -- a spurious edge can only produce a failure that a
human then reads, whereas a missed edge produces a black hole nobody sees.
"""

import ast
import os

from middlewared.alert import base as alert_base
from middlewared.alert.applicability import Applicability
from middlewared.alert.base import AlertClass
from middlewared.pytest.unit.alert.test_applicability_matrix import POPULATIONS, declarations
from middlewared.utils.python import get_middlewared_dir

SOURCE_DIR = os.path.join(get_middlewared_dir(), "alert", "source")

# The framework's own exported names, so a source mentioning ``AlertClass`` itself is not read
# as an edge. Derived from the module rather than listed here, so it cannot go stale.
FRAMEWORK_NAMES = frozenset(alert_base.__all__)


def _alert_class_reference(node: ast.AST) -> str | None:
    """The alert class a node names, whether spelled ``FooAlertClass`` or ``module.FooAlertClass``."""
    if isinstance(node, ast.Name):
        name = node.id
    elif isinstance(node, ast.Attribute):
        name = node.attr
    else:
        return None

    if name.endswith("AlertClass") and name not in FRAMEWORK_NAMES:
        return name

    return None


def _classes_a_source_may_create() -> dict[str, set[str]]:
    """Every alert class each loaded source's body could reach, keyed by source name.

    Which class definitions count as sources comes from `declarations()`, which resolves them by
    base class the way `AlertService.load` does. Deriving it from the class name instead -- a
    ``*AlertSource`` suffix -- silently dropped every source not following that convention, and
    the tree has one.
    """
    sources_by_class_name = {
        declaration.__name__: name for name, kind, declaration in declarations() if kind == "source"
    }

    edges: dict[str, set[str]] = {}
    for entry in sorted(os.listdir(SOURCE_DIR)):
        if not entry.endswith(".py"):
            continue

        with open(os.path.join(SOURCE_DIR, entry)) as f:
            tree = ast.parse(f.read())

        for node in ast.walk(tree):
            if not (isinstance(node, ast.ClassDef) and node.name in sources_by_class_name):
                continue

            names: set[str] = set()
            for child in ast.walk(node):
                if (referenced := _alert_class_reference(child)) is not None:
                    names.add(referenced.removesuffix("AlertClass"))

                # `alert.oneshot_create("<Name>", ...)` names its class as a string.
                if (
                    isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Attribute)
                    and child.func.attr in ("call", "call_sync")
                    and len(child.args) >= 2
                    and isinstance(child.args[0], ast.Constant)
                    and child.args[0].value == "alert.oneshot_create"
                    and isinstance(child.args[1], ast.Constant)
                ):
                    names.add(child.args[1].value)

            edges[sources_by_class_name[node.name]] = names

    return edges


def test_the_scan_sees_every_source_that_is_loaded():
    """A source the scan does not see is not checked below, and nothing says so.

    This is also what makes the `sources[source_name]` lookup in that check safe: the two
    modules cannot disagree about what a source is without failing here first.
    """
    loaded = {name for name, kind, _ in declarations() if kind == "source"}

    assert set(_classes_a_source_may_create()) == loaded


def test_every_source_resolves_to_at_least_one_class():
    """A source whose classes cannot be inferred is a gap in the check below, not a pass.

    Without this, a source built in a shape the scan does not model would sail through with an
    empty edge set and its black holes would go unreported.
    """
    unresolved = sorted(name for name, classes in _classes_a_source_may_create().items() if not classes)

    assert unresolved == []


def test_a_source_never_outruns_its_classes():
    """Wherever a source is ran, every class it can create must apply."""
    sources = {name: declaration for name, kind, declaration in declarations() if kind == "source"}
    applicability = [(population, Applicability(population.facts)) for population in POPULATIONS]

    holes = []
    for source_name, class_names in sorted(_classes_a_source_may_create().items()):
        source = sources[source_name]
        for class_name in sorted(class_names):
            klass = AlertClass.class_by_name[class_name]
            for population, snapshot in applicability:
                if snapshot.source_runs(source) and not snapshot.class_applies(klass):
                    holes.append(f"{source_name} runs on {population.name} but {class_name} does not apply")

    assert holes == []
