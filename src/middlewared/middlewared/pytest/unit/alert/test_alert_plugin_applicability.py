"""The applicability call sites in ``plugins/alert.py``, driven against a stub middleware.

Nothing static covers this plugin: it is not in the mypy workflow's argument list, and
``--follow-imports silent`` swallows errors in modules mypy merely follows on the way to one that
is. A rule is now a function rather than a dataclass, so a call site that reads one off an
instance or forgets to call it would type-check clean and fail at runtime. These tests are the
guard instead, one per site that asks an applicability question.
"""

import pytest

from middlewared.alert.base import Alert
from middlewared.alert.source.memory_errors import MemorySizeMismatchAlertClass
from middlewared.alert.source.scheduled_reboot import FailoverRebootAlertClass
from middlewared.plugins import alert as alert_plugin
from middlewared.plugins.alert import AlertService
from middlewared.pytest.unit.alert.harness import HA_LICENSED_FACTS, LICENSED, UNLICENSED, RecordingLogger

# An HA-only one-shot class, so a single declaration covers listing, displaying and creating.
HA_ONLY = FailoverRebootAlertClass
HA_ONLY_ARGS = {"fqdn": "tn.example.com", "now": "2026-01-01 00:00:00"}

# Applies on any iX appliance, but is only catalogued where the licence grants HA. The one shape
# where the two questions give different answers, and the only way to tell the catalogue's rule
# apart from the display rule.
UNLISTED_BUT_APPLICABLE = MemorySizeMismatchAlertClass
UNLISTED_BUT_APPLICABLE_ARGS = {"r1": "64 GiB", "r2": "32 GiB"}


class StubMiddleware:
    def __init__(self):
        self.calls = []
        self.events = []

    def event_register(self, *args, **kwargs):
        pass

    def send_event(self, *args, **kwargs):
        self.events.append(args)

    async def run_in_thread(self, fn, *args, **kwargs):
        return fn(*args, **kwargs)

    async def call(self, method, *args, **kwargs):
        self.calls.append(method)
        if method == "alertclasses.config":
            return {"classes": {}}
        if method == "alert.node_map":
            return {"A": "Controller A", "B": "Controller B"}
        if method == "alert.send_alerts":
            return None

        raise AssertionError(f"unexpected call {method!r}")


def make_service(monkeypatch, facts, reads=None):
    def get_facts():
        if reads is not None:
            reads.append(facts)
        return facts

    monkeypatch.setattr(alert_plugin, "get_facts", get_facts)

    service = AlertService(StubMiddleware())
    service.logger = RecordingLogger()
    service.node = "A"
    service.alerts = []
    return service


@pytest.mark.asyncio
async def test_the_facts_are_read_once_and_held(monkeypatch):
    reads = []
    service = make_service(monkeypatch, LICENSED, reads)

    first = await service.applicability()
    assert await service.applicability() is first
    assert len(reads) == 1


@pytest.mark.asyncio
async def test_a_license_change_drops_the_held_answers(monkeypatch):
    reads = []
    service = make_service(monkeypatch, LICENSED, reads)

    first = await service.applicability()
    await service.invalidate_applicability()

    assert await service.applicability() is not first
    assert len(reads) == 2


@pytest.mark.asyncio
async def test_an_absent_license_is_never_held(monkeypatch):
    """`get_license` returns `None` for an unlicensed system and for one whose daemon did not
    answer, and the two are indistinguishable. Holding the second would strand a licensed system
    until its next upload or reboot."""
    reads = []
    service = make_service(monkeypatch, UNLICENSED, reads)

    assert await service.applicability() is not await service.applicability()
    assert len(reads) == 2


async def listed_class_ids(service, **options):
    categories = await AlertService.list_categories(
        service, {"include_all_products": False, "include_hidden_classes": False, **options}
    )
    return {klass["id"] for category in categories for klass in category["classes"]}


@pytest.mark.asyncio
async def test_list_categories_omits_a_class_that_does_not_apply(monkeypatch):
    service = make_service(monkeypatch, LICENSED)

    assert HA_ONLY.name not in await listed_class_ids(service)


@pytest.mark.asyncio
async def test_list_categories_offers_a_class_that_applies(monkeypatch):
    service = make_service(monkeypatch, HA_LICENSED_FACTS)

    assert HA_ONLY.name in await listed_class_ids(service)


@pytest.mark.asyncio
async def test_list_categories_honours_include_all_products(monkeypatch):
    service = make_service(monkeypatch, LICENSED)

    assert HA_ONLY.name in await listed_class_ids(service, include_all_products=True)


@pytest.mark.asyncio
async def test_list_hides_an_alert_whose_class_does_not_apply(monkeypatch):
    service = make_service(monkeypatch, LICENSED)
    service.alerts = [Alert(HA_ONLY, HA_ONLY_ARGS, node="A", _uuid="alert-uuid")]

    assert await AlertService.list(service) == []


@pytest.mark.asyncio
async def test_list_shows_an_alert_whose_class_applies(monkeypatch):
    service = make_service(monkeypatch, HA_LICENSED_FACTS)
    service.alerts = [Alert(HA_ONLY, HA_ONLY_ARGS, node="A", _uuid="alert-uuid")]

    assert [alert["klass"] for alert in await AlertService.list(service)] == [HA_ONLY.name]


@pytest.mark.asyncio
async def test_oneshot_create_reports_a_class_that_cannot_be_shown(monkeypatch):
    """The black hole: the alert is stored and then denied everywhere it would be displayed.

    Both rules are named, because the whole question is which of the two is wrong, and neither is
    visible from the alert itself. Naming them is only possible because a rule is a function.
    """
    alert_plugin._REPORTED_INAPPLICABLE_CLASSES.clear()
    service = make_service(monkeypatch, LICENSED)

    await AlertService.oneshot_create(service, object(), HA_ONLY.name, HA_ONLY_ARGS)

    assert len(service.alerts) == 1
    assert len(service.logger.errors) == 1
    assert "the class to HA_LICENSED" in service.logger.errors[0]


@pytest.mark.asyncio
async def test_oneshot_create_is_quiet_where_the_class_applies(monkeypatch):
    alert_plugin._REPORTED_INAPPLICABLE_CLASSES.clear()
    service = make_service(monkeypatch, HA_LICENSED_FACTS)

    await AlertService.oneshot_create(service, object(), HA_ONLY.name, HA_ONLY_ARGS)

    assert len(service.alerts) == 1
    assert service.logger.errors == []


@pytest.mark.asyncio
async def test_the_catalogue_drops_a_class_it_still_displays(monkeypatch):
    """`listed_only_when` takes a class out of the catalogue and out of nothing else.

    Every other class in this module is either listed and displayed or neither, which is why
    reading the wrong one of the two rules in `list_categories` goes unnoticed. This is the one
    declaration in the tree where the two answers differ, so it is the only place the catalogue's
    rule can be told apart from the display rule through production code.
    """
    service = make_service(monkeypatch, LICENSED)
    service.alerts = [Alert(UNLISTED_BUT_APPLICABLE, UNLISTED_BUT_APPLICABLE_ARGS, node="A", _uuid="alert-uuid")]

    assert UNLISTED_BUT_APPLICABLE.name not in await listed_class_ids(service)
    assert [alert["klass"] for alert in await AlertService.list(service)] == [UNLISTED_BUT_APPLICABLE.name]


@pytest.mark.asyncio
async def test_the_catalogue_offers_it_once_the_licence_grants_ha(monkeypatch):
    service = make_service(monkeypatch, HA_LICENSED_FACTS)

    assert UNLISTED_BUT_APPLICABLE.name in await listed_class_ids(service)
