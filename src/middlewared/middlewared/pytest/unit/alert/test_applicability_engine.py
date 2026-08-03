import pytest
from truenas_pylicensed import LicenseType

from middlewared.alert.applicability import (
    ANY_LICENSE,
    APPLIANCE_OR_HA_LICENSED,
    EXPECTED_TO_BE_LICENSED,
    HA_LICENSED,
    MINI_HARDWARE,
    NOT_APPLIANCE_HARDWARE,
    TRUENAS_HARDWARE,
    Applicability,
    applies,
    declaration_rule_name,
    vocabulary,
)
from middlewared.alert.applicability.engine import rule_name
from middlewared.pytest.unit.utils.test_entitlements import make_license
from middlewared.utils.entitlements import DerivedEntitlement, EntitlementFacts, check_entitlement
from middlewared.utils.hardware import HardwareClass

NO_LICENSE = None
PLAIN_LICENSE = make_license(type_=LicenseType.ENTERPRISE_SINGLE)
HA_LICENSE = make_license(type_=LicenseType.ENTERPRISE_HA)

# Every axis value the two facts can take, so a grid below is exhaustive by construction.
HARDWARE_CLASSES = (HardwareClass.TRUENAS_HW, HardwareClass.MINI, HardwareClass.GENERIC)
LICENSES = (NO_LICENSE, PLAIN_LICENSE, HA_LICENSE)

# Every shipped population, spelled out against every system it can be asked about. One row per
# hardware class in the order above; one cell per license in the order above; ``Y`` where the
# population covers that system. These are the objects the tree's declarations actually carry, so
# a cell here is the answer a real declaration gets, not the answer a copy of the rule would give.
# fmt: off
GRIDS = (
    #                          TRUENAS_HW  MINI    GENERIC   -- and within each, unlicensed/plain/HA
    (TRUENAS_HARDWARE,         "YYY",      "...",  "..."),
    (MINI_HARDWARE,            "...",      "YYY",  "..."),
    (NOT_APPLIANCE_HARDWARE,   "...",      "YYY",  "YYY"),
    (ANY_LICENSE,              ".YY",      ".YY",  ".YY"),
    (HA_LICENSED,              "..Y",      "..Y",  "..Y"),
    (APPLIANCE_OR_HA_LICENSED, "YYY",      "..Y",  "..Y"),
    (EXPECTED_TO_BE_LICENSED,  "YYY",      ".YY",  ".YY"),
)
# fmt: on

CASES = [
    (rule, hardware_class, license, cell == "Y")
    for rule, *rows in GRIDS
    for hardware_class, row in zip(HARDWARE_CLASSES, rows, strict=True)
    for license, cell in zip(LICENSES, row, strict=True)
]

CASE_IDS = [
    f"{rule.__name__}-{hardware_class.value}-{'ha' if license is HA_LICENSE else 'plain' if license else 'none'}"
    for rule, hardware_class, license, _ in CASES
]


def make_facts(hardware_class, license):
    return EntitlementFacts(hardware_class=hardware_class, license=license)


def test_the_grid_covers_every_shipped_population():
    """A population added without a row here would ship with nothing saying what it covers."""
    assert {rule.__name__ for rule, *_ in GRIDS} == set(vocabulary.__all__)


@pytest.mark.parametrize("rule,hardware_class,license,expected", CASES, ids=CASE_IDS)
def test_applies(rule, hardware_class, license, expected):
    assert applies(rule, make_facts(hardware_class, license)) is expected


@pytest.mark.parametrize("hardware_class", HARDWARE_CLASSES)
@pytest.mark.parametrize("license", LICENSES)
def test_an_undeclared_rule_states_no_constraint(hardware_class, license):
    assert applies(None, make_facts(hardware_class, license)) is True


def test_ha_matches_the_entitlement_policy():
    """HA is not reimplemented here: it has to be the same answer the entitlement policy gives.

    Asked of the shipped ``HA_LICENSED`` rather than a copy of it, so this proves the name every
    HA declaration in the tree carries resolves to the policy's answer.
    """
    for hardware_class in HardwareClass:
        for license in (NO_LICENSE, PLAIN_LICENSE, HA_LICENSE):
            entitlement = check_entitlement(
                DerivedEntitlement.HA,
                EntitlementFacts(hardware_class=hardware_class, license=license),
            )
            assert applies(HA_LICENSED, make_facts(hardware_class, license)) is entitlement.entitled


class HardwareOnlyDeclaration:
    applies_to = TRUENAS_HARDWARE
    listed_only_when = None


class NarrowedDeclaration:
    applies_to = TRUENAS_HARDWARE
    listed_only_when = HA_LICENSED


class UnconstrainedDeclaration:
    applies_to = None
    listed_only_when = None


def test_rule_name_reports_the_population_a_declaration_named():
    """The name is what makes a rule readable in a log; a dataclass instance would not carry one."""
    assert rule_name(TRUENAS_HARDWARE) == "TRUENAS_HARDWARE"
    assert rule_name(None) == "unconstrained"
    assert declaration_rule_name(HardwareOnlyDeclaration) == "TRUENAS_HARDWARE"
    assert declaration_rule_name(UnconstrainedDeclaration) == "unconstrained"


def test_applicability_answers_all_three_questions():
    appliance = Applicability(make_facts(HardwareClass.TRUENAS_HW, PLAIN_LICENSE))

    assert appliance.class_applies(HardwareOnlyDeclaration) is True
    assert appliance.class_listed(HardwareOnlyDeclaration) is True
    assert appliance.source_runs(HardwareOnlyDeclaration) is True

    # listed_only_when narrows the catalogue and nothing else.
    assert appliance.class_applies(NarrowedDeclaration) is True
    assert appliance.class_listed(NarrowedDeclaration) is False

    assert appliance.class_applies(UnconstrainedDeclaration) is True
    assert appliance.class_listed(UnconstrainedDeclaration) is True
    assert appliance.source_runs(UnconstrainedDeclaration) is True


def test_applicability_evaluates_each_declaration_once():
    calls = []

    def COUNTED(facts):
        calls.append(facts)
        return True

    class Declared:
        applies_to = COUNTED
        listed_only_when = None

    applicability = Applicability(make_facts(HardwareClass.GENERIC, NO_LICENSE))

    assert applicability.class_applies(Declared) is True
    assert applicability.class_applies(Declared) is True
    assert applicability.source_runs(Declared) is True
    assert applicability.source_runs(Declared) is True

    # Once for the class question, once for the source question: they are separate answers about
    # separate declarations in the tree and share no memo.
    assert len(calls) == 2


def test_applicability_holds_one_reading_of_the_facts():
    facts = make_facts(HardwareClass.TRUENAS_HW, NO_LICENSE)

    assert Applicability(facts).facts is facts


@pytest.mark.parametrize(
    "hardware_class,license,expected",
    [
        (HardwareClass.TRUENAS_HW, NO_LICENSE, False),
        (HardwareClass.TRUENAS_HW, HA_LICENSE, True),
        (HardwareClass.GENERIC, HA_LICENSE, True),
        (HardwareClass.GENERIC, PLAIN_LICENSE, False),
    ],
)
def test_distinct_facts_give_distinct_answers(hardware_class, license, expected):
    """The memo is keyed on the declaration, so each snapshot has to answer for its own facts."""

    class HaDeclaration:
        applies_to = HA_LICENSED
        listed_only_when = None

    assert Applicability(make_facts(hardware_class, license)).class_applies(HaDeclaration) is expected


def test_a_rule_is_read_off_the_class_never_an_instance():
    """A rule is a function, so an instance read would bind the instance as its first argument.

    ``ALERT_SOURCES`` holds instances, which is why ``source_runs`` takes the class.
    """
    facts = make_facts(HardwareClass.TRUENAS_HW, NO_LICENSE)
    instance = HardwareOnlyDeclaration()

    assert Applicability(facts).source_runs(type(instance)) is True

    with pytest.raises(TypeError):
        instance.applies_to(facts)
