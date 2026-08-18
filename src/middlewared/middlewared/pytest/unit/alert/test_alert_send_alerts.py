"""`send_alerts` decides twice: which alerts leave the box, and whether iX is told about them.

Both decisions were unreachable from this tree -- the whole method could be replaced with a
`raise` and the suite stayed green -- so an applicability rule read wrongly here would ship. It
is the last stop before an alert reaches an operator's mailbox or opens a support ticket.

`is_applicable` is read three times, over `alerts`, `gone` and `new`, and the event bus asks the
same question a fourth time through `should_show_alert`. All four are asserted together, because
the failure that matters is one of them disagreeing with the rest.
"""

import pytest
from truenas_pylicensed.features import LicenseFeature

from middlewared.alert.base import Alert, AlertService as BaseAlertService
from middlewared.alert.source.memory_errors import MemorySizeMismatchAlertClass
from middlewared.alert.source.scheduled_reboot import FailoverRebootAlertClass
from middlewared.plugins import alert as alert_plugin
from middlewared.plugins.alert import ALERT_SERVICES_FACTORIES, AlertService
from middlewared.pytest.unit.alert.harness import LICENSED, RecordingLogger, RecordingPolicy
from middlewared.pytest.unit.entitlements import facts_for_column, install_entitlements
from middlewared.pytest.unit.helpers import create_service
from middlewared.pytest.unit.middleware import FakeJob, Middleware
from middlewared.utils.time_utils import utc_now

# Applies on any iX appliance, and asks for a proactive support ticket.
APPLICABLE = MemorySizeMismatchAlertClass
# Applies only where the licence grants HA, so on the appliances below it never does.
INAPPLICABLE = FailoverRebootAlertClass

SERVICE_DESC = {
    "id": 1,
    "type": "Recorder",
    "enabled": True,
    # The lowest level there is, so nothing is dropped for being unimportant and every exclusion
    # below is an applicability decision.
    "level": "INFO",
    "attributes": {"type": "Recorder"},
}


def make_alert(klass, args, uuid):
    return Alert(klass, args, node="A", dismissed=False, _uuid=uuid)


def _support_is_out_of_reach():
    raise AssertionError("the proactive-support block was entered on a licence that grants no support")


def install_recorder(monkeypatch):
    """Register an alert service that records what it was handed.

    The factory is called afresh for every send, so the recording has to outlive the instance.
    """
    sent = []

    class RecorderAlertService(BaseAlertService):
        title = "Recorder"

        async def send(self, alerts, gone_alerts, new_alerts):
            sent.append((alerts, gone_alerts, new_alerts))

    monkeypatch.setitem(ALERT_SERVICES_FACTORIES, "Recorder", RecorderAlertService)
    return sent


def make_service(monkeypatch, middleware, facts, alerts, remembered=()):
    monkeypatch.setattr(alert_plugin, "get_facts", lambda: facts)
    monkeypatch.setattr(alert_plugin, "SEND_ALERTS_ON_READY", False)

    middleware["system.state"] = lambda: "READY"
    middleware["alertclasses.config"] = lambda: {"classes": {}}
    middleware["alert.node_map"] = lambda: {"A": "Controller A", "B": "Controller B"}
    middleware["alertservice.query"] = lambda filters: [SERVICE_DESC]

    service = create_service(middleware, AlertService)
    service.logger = RecordingLogger()
    service.node = "A"
    service.alerts = list(alerts)
    service.policies = {
        "IMMEDIATELY": RecordingPolicy(),
        "HOURLY": RecordingPolicy(lambda d: (d.date(), d.hour)),
        "DAILY": RecordingPolicy(lambda d: d.date()),
        "NEVER": RecordingPolicy(lambda d: None),
    }
    # What the policies were last told, so this send has something to report as gone. Only the
    # IMMEDIATELY policy's key changes between then and now, so it is the only one that reports.
    for policy in service.policies.values():
        policy.receive_alerts(utc_now(), list(remembered))

    return service


@pytest.mark.asyncio
async def test_send_alerts_skips_an_alert_whose_class_does_not_apply(monkeypatch):
    middleware = Middleware()
    sent = install_recorder(monkeypatch)
    # The live entitlement engine, not the auto-`Mock` on `middleware.services`, whose truthy
    # `.entitled` would open the proactive-support gate on a licence that grants no support.
    install_entitlements(middleware, LICENSED)
    middleware["support.is_available_and_enabled"] = _support_is_out_of_reach

    service = make_service(
        monkeypatch,
        middleware,
        LICENSED,
        alerts=[
            make_alert(APPLICABLE, {"r1": "64 GiB", "r2": "32 GiB"}, "new-applicable"),
            make_alert(INAPPLICABLE, {"fqdn": "tn.example.com", "now": "2026-01-02 00:00:00"}, "new-inapplicable"),
        ],
        remembered=[
            make_alert(APPLICABLE, {"r1": "64 GiB", "r2": "16 GiB"}, "gone-applicable"),
            make_alert(INAPPLICABLE, {"fqdn": "tn.example.com", "now": "2026-01-01 00:00:00"}, "gone-inapplicable"),
        ],
    )

    await AlertService.send_alerts(service, FakeJob())

    [(alerts, gone_alerts, new_alerts)] = sent
    assert [alert.uuid for alert in alerts] == ["new-applicable"]
    assert [alert.uuid for alert in gone_alerts] == ["gone-applicable"]
    assert [alert.uuid for alert in new_alerts] == ["new-applicable"]

    announced = [(call.args[1], call.kwargs["id"]) for call in middleware.send_event.mock_calls]
    assert announced == [("REMOVED", "gone-applicable"), ("ADDED", "new-applicable")]

    assert service.logger.errors == []


@pytest.mark.asyncio
@pytest.mark.parametrize("column,entitled", [("HW+K", True), ("HW", False)])
async def test_the_proactive_support_ticket_is_gated_on_the_support_entitlement(monkeypatch, column, entitled):
    """Filing a ticket with iX is the one thing here that leaves the customer's network.

    The alert itself is unaffected either way -- it is still recorded and still announced. Only
    the ticket is gated, so the assertion is on whether the support configuration was consulted
    at all.
    """
    middleware = Middleware()
    install_recorder(monkeypatch)
    facts = facts_for_column(LicenseFeature.SUPPORT, column)
    checked = install_entitlements(middleware, facts)

    consulted = []

    def is_available_and_enabled():
        consulted.append(True)
        # False, so nothing goes on to open a real ticket.
        return False

    middleware["support.is_available_and_enabled"] = is_available_and_enabled

    service = make_service(
        monkeypatch,
        middleware,
        facts,
        alerts=[make_alert(APPLICABLE, {"r1": "64 GiB", "r2": "32 GiB"}, "proactive")],
    )

    await AlertService.send_alerts(service, FakeJob())

    assert checked == [LicenseFeature.SUPPORT]
    assert bool(consulted) is entitled
