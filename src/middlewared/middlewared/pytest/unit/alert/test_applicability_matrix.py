"""The review artifact for the alert applicability migration.

Every alert declaration used to be gated by ``system.product_type``, a predicate that conflated a
chassis probe with a license read. Each declaration now states its own rule on one of two
independent axes, so the populations it covers necessarily move. Those moves are the deliverable,
not an accident, and they are reviewed here: this module regenerates a fixed-width table of the old
answer against the new one for every declaration in ``alert/source``, and fails on any difference
from the checked-in copy. One declaration changing rule touches one line of that file.

The old predicate is reimplemented below rather than called. It is being removed from production
code, and reproducing it there as a shim was the thing this work set out not to do.

Regenerate with ``ALERT_MATRIX_REGENERATE=1 pytest .../test_applicability_matrix.py`` and read the
resulting diff.
"""

import ast
import os
from dataclasses import dataclass

import pytest
from truenas_pylicensed import LicenseType

from middlewared.alert.applicability import AlertFacts, HardwareClass, LicenseRequirement, LicenseRule, applies
from middlewared.alert.base import AlertCategory, AlertClass, AlertSource, ThreadedAlertSource
from middlewared.plugins.alert import should_list_alert_class
from middlewared.pytest.unit.utils.test_entitlements import make_license
from middlewared.utils import ProductType
from middlewared.utils.license import LicenseInfo
from middlewared.utils.plugins import load_classes, load_modules
from middlewared.utils.python import get_middlewared_dir

GOLDEN = os.path.join(os.path.dirname(__file__), "golden", "applicability.txt")
SOURCE_PACKAGE = "middlewared.alert.source."
HA_LICENSED = LicenseRule(requirement=LicenseRequirement.HA)


@dataclass(frozen=True, kw_only=True, slots=True)
class Population:
    """A system the matrix is evaluated against.

    ``ha_capable`` is here for the old predicate alone -- it is a chassis probe that the new axes
    deliberately do not carry, and it is not part of ``AlertFacts``.
    """

    name: str
    description: str
    hardware_class: HardwareClass
    license: LicenseInfo | None
    ha_capable: bool

    @property
    def facts(self) -> AlertFacts:
        return AlertFacts(hardware_class=self.hardware_class, license=self.license)


POPULATIONS = (
    Population(
        name="G",
        description="whitebox, unlicensed",
        hardware_class=HardwareClass.GENERIC,
        license=None,
        ha_capable=False,
    ),
    Population(
        name="C0",
        description="Mini, unlicensed",
        hardware_class=HardwareClass.MINI,
        license=None,
        ha_capable=False,
    ),
    Population(
        name="C",
        description="Mini with a MINI-R license",
        hardware_class=HardwareClass.MINI,
        license=make_license(model="MINI-R"),
        ha_capable=False,
    ),
    Population(
        name="A",
        description="iX appliance reading MANUAL, unlicensed (R-series)",
        hardware_class=HardwareClass.TRUENAS_HW,
        license=None,
        ha_capable=False,
    ),
    Population(
        name="B",
        description="iX appliance with a FREENAS-CERTIFIED license",
        hardware_class=HardwareClass.TRUENAS_HW,
        license=make_license(model="FREENAS-CERTIFIED"),
        ha_capable=False,
    ),
    Population(
        name="Di",
        description="whitebox with a transplanted M50 license",
        hardware_class=HardwareClass.GENERIC,
        license=make_license(model="M50"),
        ha_capable=False,
    ),
    Population(
        name="HA",
        description="iX appliance with an HA license",
        hardware_class=HardwareClass.TRUENAS_HW,
        license=make_license(model="M50", type_=LicenseType.ENTERPRISE_HA),
        ha_capable=True,
    ),
)


def old_product_type(population: Population) -> str:
    """``system.product_type`` as it stands today (``plugins/system/product.py``).

    Six lines, kept in the test fixture on purpose: the point of the migration is that no production
    code answers this question any more.
    """
    if population.ha_capable:
        return ProductType.ENTERPRISE

    license = population.license
    if license is not None and license.model is not None and not license.model.lower().startswith("freenas"):
        return ProductType.ENTERPRISE

    return ProductType.COMMUNITY_EDITION


def old_listed(declaration, population: Population) -> bool:
    """``should_list_alert_class`` as it stands today, including the undeclared `AlertCategory.HA` hack."""
    if declaration.category == AlertCategory.HA and not applies(HA_LICENSED, population.facts):
        return False

    return old_product_type(population) in declaration.products


def declarations():
    """Every declaration in ``alert/source``, loaded the way ``AlertService.load`` loads it.

    Classes appear twice: once for applicability -- running, displaying and sending -- and once for
    the settings catalogue, which `listed_when` narrows further and which nothing else consults.
    """
    sources = []
    for module in load_modules(os.path.join(get_middlewared_dir(), "alert", "source")):
        for cls in load_classes(module, AlertSource, (ThreadedAlertSource,)):
            sources.append((cls.__name__.replace("AlertSource", ""), "source", cls))

    classes = [
        (cls.name, kind, cls)
        for cls in AlertClass.classes
        if cls.__module__.startswith(SOURCE_PACKAGE)
        for kind in ("class", "listed")
    ]

    return sorted(set(sources + classes), key=lambda row: (row[0], row[1]))


def answers(kind: str, declaration, population: Population) -> tuple[bool, bool]:
    if kind == "listed":
        return old_listed(declaration, population), should_list_alert_class(declaration, population.facts)

    return old_product_type(population) in declaration.products, applies(declaration.applies_to, population.facts)


def cell(old: bool, new: bool) -> str:
    """``<old><new><marker>``: ``Y`` applies, ``.`` does not, ``+``/``-`` where the answer moved."""
    marker = " " if old == new else ("+" if new else "-")
    return f"{'Y' if old else '.'}{'Y' if new else '.'}{marker}"


def render() -> str:
    lines = [
        "# Alert applicability: today's product_type gate (old) against the declared rule (new).",
        "# Each cell is <old><new><marker>: Y applies, . does not, + gained, - lost.",
        "# Generated by test_applicability_matrix.py -- do not edit by hand.",
        "#",
        "# Kinds: class  -- the class applies: displayed, sent, and offered in the catalogue",
        "#        listed -- the class is offered in the settings catalogue, which listed_when narrows",
        "#        source -- the source is ran",
        "#",
        "# Populations:",
    ]
    for population in POPULATIONS:
        lines.append(
            f"#   {population.name:<4} {population.hardware_class.value:<11} "
            f"{'licensed' if population.license is not None else 'unlicensed':<10} "
            f"{'ha_capable' if population.ha_capable else '':<10} {population.description}"
        )
    lines.append("")

    header = f"{'DECLARATION':<44}{'KIND':<8}"
    header += "".join(f"{population.name:<5}" for population in POPULATIONS)
    lines.append(header.rstrip())

    for name, kind, declaration in declarations():
        row = f"{name:<44}{kind:<8}"
        for population in POPULATIONS:
            row += f"{cell(*answers(kind, declaration, population)):<5}"
        lines.append(row.rstrip())

    return "\n".join(lines) + "\n"


def test_applicability_matrix():
    """Fails on any population change, so every one of them is read in review."""
    matrix = render()

    if os.environ.get("ALERT_MATRIX_REGENERATE"):
        os.makedirs(os.path.dirname(GOLDEN), exist_ok=True)
        with open(GOLDEN, "w") as f:
            f.write(matrix)

    with open(GOLDEN) as f:
        assert f.read() == matrix, "alert applicability changed; regenerate with ALERT_MATRIX_REGENERATE=1"


def test_every_declaration_carries_a_rule():
    """A declaration left without a rule silently widens to every system, and reads as intentional."""
    unruled = [
        (name, kind)
        for name, kind, declaration in declarations()
        if kind != "listed"
        and declaration.products != (ProductType.COMMUNITY_EDITION, ProductType.ENTERPRISE)
        and declaration.applies_to is None
        and getattr(declaration, "listed_when", None) is None
    ]
    assert unruled == []


@pytest.mark.parametrize(
    "class_name",
    [
        "FailoverFailed",
        "FailoverSyncFailed",
        "MemorySizeMismatch",
    ],
)
def test_listed_when_hides_without_silencing(class_name):
    """An HA class on a non-HA-licensed system leaves the catalogue, and nothing else.

    The scheduled-reboot classes are deliberately not in this set: they are gated on the HA license
    itself, so on a system without one they are silenced rather than merely unlisted.
    """
    facts = AlertFacts(hardware_class=HardwareClass.TRUENAS_HW, license=make_license(model="M50"))
    klass = AlertClass.class_by_name[class_name]

    assert applies(klass.applies_to, facts) is True
    assert should_list_alert_class(klass, facts) is False


def test_listed_when_is_only_read_when_listing():
    """``listed_when`` narrows the catalogue and nothing else, and only ``should_list_alert_class``
    is entitled to read it. Anywhere else it would silence alerts that already exist."""
    import middlewared.plugins.alert as alert_plugin

    with open(alert_plugin.__file__) as f:
        tree = ast.parse(f.read())

    reads = [node for node in ast.walk(tree) if isinstance(node, ast.Attribute) and node.attr == "listed_when"]

    readers = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(node):
                if isinstance(child, ast.Attribute) and child.attr == "listed_when":
                    readers.add(node.name)

    assert len(reads) == 1
    assert readers == {"should_list_alert_class"}
