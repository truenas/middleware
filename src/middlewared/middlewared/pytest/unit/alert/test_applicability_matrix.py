"""The frozen inventory of what every alert declaration applies to.

An alert's applicability is declared on two independent axes -- hardware class and license -- and
is otherwise invisible: nothing in the alert itself says which systems will ever see it. This
module renders that answer for every declaration in the tree against a fixed set of populations,
and fails on any difference from the checked-in copy. Changing one declaration's rule
touches one line of that file, so a population change cannot land without being read in review.

Regenerate with ``ALERT_MATRIX_REGENERATE=1 pytest .../test_applicability_matrix.py`` and read the
resulting diff.
"""

import ast
import importlib
import os
from dataclasses import dataclass

import pytest
from truenas_pylicensed import LicenseType

from middlewared.alert.applicability import HA_LICENSED, Applicability, applies, applies_for_listing, vocabulary
from middlewared.alert.base import AlertCategory, AlertClass, AlertSource, ThreadedAlertSource
from middlewared.pytest.unit.entitlements import make_license
from middlewared.utils.entitlements import EntitlementFacts
from middlewared.utils.hardware import HardwareClass
from middlewared.utils.license import LicenseInfo
from middlewared.utils.plugins import load_classes, load_modules
from middlewared.utils.python import get_middlewared_dir

INVENTORY_FILE = os.path.join(os.path.dirname(__file__), "inventory", "applicability.txt")


@dataclass(frozen=True, kw_only=True, slots=True)
class Population:
    """A system the inventory is evaluated against.

    ``ha_capable`` is descriptive only. It is a chassis probe that the axes deliberately do not
    carry, and it is not part of ``EntitlementFacts``; it is recorded so the populations read as
    real machines.
    """

    name: str
    description: str
    hardware_class: HardwareClass
    license: LicenseInfo | None
    ha_capable: bool

    @property
    def facts(self) -> EntitlementFacts:
        return EntitlementFacts(hardware_class=self.hardware_class, license=self.license)


# GENERIC+HA and MINI+HA are absent deliberately. A machine can only reach them two ways: as a
# Mini-tagged HA virtual machine, where classify_platform reads the chassis before the QEMU stamp
# while detect_platform reads the QEMU stamp first, so the two disagree; or with a legacy
# /data/license blob hand-placed on non-iX hardware. Neither exists in the fleet, and a population
# no machine occupies would freeze answers nobody can check against a real system.
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


def _base_name(base: ast.expr) -> str | None:
    """The name of a base class as written, whether spelled ``AlertClass`` or ``base.AlertClass``.

    A scan blind to one of the two spellings does not report a gap: it simply never looks at the
    module, and every declaration in it drops out of the inventory silently.
    """
    if isinstance(base, ast.Name):
        return base.id

    if isinstance(base, ast.Attribute):
        return base.attr

    return None


def _modules_declaring_alert_classes() -> list[str]:
    """Every module in the tree that declares an ``AlertClass``, found without importing it.

    ``AlertClass.classes`` is filled by the metaclass at import time, so what is in it depends on
    what has been imported. Scanning first and importing the result makes the inventory the same
    whatever else the test session touched, and picks up a class declared in a plugin the day it is
    written rather than the day someone remembers to add it here.
    """
    root = get_middlewared_dir()
    modules = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ("__pycache__", "pytest", "alembic")]
        for filename in filenames:
            if not filename.endswith(".py"):
                continue

            path = os.path.join(dirpath, filename)
            with open(path) as f:
                tree = ast.parse(f.read())

            if any(
                isinstance(node, ast.ClassDef) and any(_base_name(base) == "AlertClass" for base in node.bases)
                for node in ast.walk(tree)
            ):
                relative = os.path.relpath(path, root).removesuffix(".py").replace(os.sep, ".")
                modules.append(f"middlewared.{relative}")

    return sorted(modules)


def test_the_scan_reaches_every_module_that_declares_a_class():
    """Whatever the metaclass registered, the scan has to have found the module it came from.

    The scan decides what gets imported, so on its own it could agree with the registry by
    keeping both empty. It cannot here: `declarations()` loads every module under
    ``alert/source`` through `load_modules`, independently of this scan, and that is where
    almost every alert class in the tree lives. A module the scan cannot read is therefore in
    the registry and not in its result, and this is the only thing that says so.
    """
    declarations()

    scanned = set(_modules_declaring_alert_classes())
    registered = {
        klass.__module__ for klass in AlertClass.classes if not klass.__module__.startswith("middlewared.pytest.")
    }

    assert registered - scanned == set()


def declarations():
    """Every alert declaration in the tree, source and class alike.

    Classes appear twice: once for applicability -- running, displaying and sending -- and once for
    the settings catalogue, which `listed_only_when` narrows further and which nothing else
    consults.
    """
    sources = []
    for module in load_modules(os.path.join(get_middlewared_dir(), "alert", "source")):
        for cls in load_classes(module, AlertSource, (ThreadedAlertSource,)):
            sources.append((cls.__name__.removesuffix("AlertSource"), "source", cls))

    for name in _modules_declaring_alert_classes():
        importlib.import_module(name)

    classes = [(cls.name, kind, cls) for cls in AlertClass.classes for kind in ("class", "listed")]

    return sorted(set(sources + classes), key=lambda row: (row[0], row[1]))


def answer(kind: str, declaration, applicability: Applicability) -> bool:
    """Asked of the production path, so the frozen artifact cannot drift from what the daemon does."""
    if kind == "listed":
        return applicability.class_listed(declaration)

    if kind == "source":
        return applicability.source_runs(declaration)

    return applicability.class_applies(declaration)


def render() -> str:
    lines = [
        "# Alert applicability: the systems each declaration's rule covers.",
        "# Each cell is Y where the declaration applies and . where it does not.",
        "# Generated by test_applicability_matrix.py -- do not edit by hand.",
        "#",
        "# Kinds: class  -- the class applies: displayed, sent, and offered in the catalogue",
        "#        listed -- the class is offered in the settings catalogue, which listed_only_when narrows",
        "#        source -- the source's rule admits this system. Whether it is actually ran also",
        "#                  turns on gates this matrix does not model: post_failover_blackout,",
        "#                  require_stable_peer, the source's schedule, and source locks.",
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
    header += "".join(f"{population.name:<4}" for population in POPULATIONS)
    lines.append(header.rstrip())

    applicability = [Applicability(population.facts) for population in POPULATIONS]

    for name, kind, declaration in declarations():
        row = f"{name:<44}{kind:<8}"
        for snapshot in applicability:
            row += f"{'Y' if answer(kind, declaration, snapshot) else '.':<4}"
        lines.append(row.rstrip())

    return "\n".join(lines) + "\n"


def test_applicability_matrix():
    """Fails on any population change, so every one of them is read in review."""
    matrix = render()

    if os.environ.get("ALERT_MATRIX_REGENERATE"):
        os.makedirs(os.path.dirname(INVENTORY_FILE), exist_ok=True)
        with open(INVENTORY_FILE, "w") as f:
            f.write(matrix)

    with open(INVENTORY_FILE) as f:
        assert f.read() == matrix, "alert applicability changed; regenerate with ALERT_MATRIX_REGENERATE=1"


def frozen_inventory() -> dict[tuple[str, str], list[str]]:
    """The checked-in file, parsed. Deliberately not ``render()``: the point is to compare the tree
    against what was last reviewed, not against itself."""
    inventory = {}
    with open(INVENTORY_FILE) as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#") or line.startswith("DECLARATION"):
                continue

            inventory[(line[:44].strip(), line[44:52].strip())] = line[52:].split()

    return inventory


def test_every_declaration_carries_a_rule():
    """A declaration left without a rule silently widens to every system, and reads as intentional.

    Every declaration the frozen inventory records as restricted anywhere must still hold a rule
    saying so. Deleting one and regenerating the inventory defeats this, which is the intent: the
    regeneration is what lands in the diff.
    """
    inventory = frozen_inventory()
    live = {(name, kind): declaration for name, kind, declaration in declarations()}
    assert set(inventory) == set(live), "the frozen inventory does not describe this tree; regenerate it"

    unruled = []
    for (name, kind), cells in inventory.items():
        if all(cell == "Y" for cell in cells):
            continue

        declaration = live[(name, kind)]
        rule = declaration.applies_to
        if kind == "listed":
            rule = rule or declaration.listed_only_when

        if rule is None:
            unruled.append((name, kind))

    assert unruled == []


@pytest.mark.parametrize(
    "class_name",
    [
        "FailoverFailed",
        "FailoverSyncFailed",
        "MemorySizeMismatch",
    ],
)
def test_listed_only_when_hides_without_silencing(class_name):
    """An HA class on a non-HA-licensed system leaves the catalogue, and nothing else.

    The scheduled-reboot classes are deliberately not in this set: they are gated on the HA license
    itself, so on a system without one they are silenced rather than merely unlisted.
    """
    facts = EntitlementFacts(hardware_class=HardwareClass.TRUENAS_HW, license=make_license(model="M50"))
    klass = AlertClass.class_by_name[class_name]

    assert applies(klass.applies_to, facts) is True
    assert applies_for_listing(klass, facts) is False


def test_every_rule_is_a_vocabulary_name():
    """A declaration names a population; it does not build one.

    ``vocabulary`` says so in prose and nothing enforced it. Rules are ordinary functions now, so
    an inline lambda or a one-off predicate written at a declaration site would work perfectly and
    would put a population nobody reviewed in front of a hundred machines. This is also the only
    guard over the declaration sites themselves: mypy does not check ``alert/source/``.
    """
    populations = {getattr(vocabulary, name) for name in vocabulary.__all__}

    strays = []
    for name, kind, declaration in declarations():
        for attribute in ("applies_to", "listed_only_when"):
            rule = getattr(declaration, attribute, None)
            if rule is not None and rule not in populations:
                strays.append(f"{name} {kind} {attribute}={rule!r}")

    assert strays == []


@pytest.mark.parametrize("attribute", ["applies_to", "listed_only_when"])
def test_rules_are_read_only_where_applicability_is_decided(attribute):
    """Applicability is decided in one place, and ``listed_only_when`` in one narrower place.

    Read anywhere but the applicability engine, ``listed_only_when`` would silence alerts that
    already exist, and a second reader of ``applies_to`` is a second answer that can disagree with
    the one ``Applicability`` gives. So this is a whole-tree check rather than a check of one file:
    a second reader cannot appear without this failing. Declarations are unaffected -- assigning
    the attribute in a class body is a plain name, not an attribute access. The unit-test tree is
    excluded: the frozen inventory reads the attribute to check that a restricted declaration still
    carries a rule, which is bookkeeping about declarations rather than an enforcement point.
    """
    allowed = (os.path.join("alert", "applicability"), os.path.join("alert", "base.py"))
    root = get_middlewared_dir()

    readers = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in ("__pycache__", "pytest", "alembic")]
        for filename in filenames:
            if not filename.endswith(".py"):
                continue

            path = os.path.join(dirpath, filename)
            with open(path) as f:
                tree = ast.parse(f.read())

            if any(isinstance(node, ast.Attribute) and node.attr == attribute for node in ast.walk(tree)):
                readers.add(os.path.relpath(path, root))

    assert {reader for reader in readers if not reader.startswith(allowed)} == set()


def test_ha_classes_are_not_listed_without_an_ha_license():
    """The old code hid every HA-category class on a system without an HA license, implicitly.

    That rule is now hand-written on each of them, and ``test_every_declaration_carries_a_rule``
    does not catch a new class that forgets it: a declaration whose inventory row is all ``Y`` is
    skipped there, and an all-``Y`` row is exactly what forgetting looks like.
    """
    unlisted_populations = [p for p in POPULATIONS if not applies(HA_LICENSED, p.facts)]
    assert unlisted_populations, "no population without an HA license; this test proves nothing"

    listed = [
        (klass.name, population.name)
        for klass in AlertClass.classes
        if klass.category is AlertCategory.HA
        for population in unlisted_populations
        if applies_for_listing(klass, population.facts)
    ]

    assert listed == []
