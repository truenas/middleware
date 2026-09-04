import contextlib
import json

import pytest
from auto_config import ha, pool_name
from middlewared.test.integration.utils import call, mock, ssh
from middlewared.test.integration.utils.alert import (
    alert_classes,
    get_alerts_by_class,
    remove_oneshot_alerts,
    run_alerts,
    wait_for_alerts_by_class,
)

pytestmark = pytest.mark.skipif(not ha, reason="Proactive Support is only available on Enterprise HA systems")

# `ZpoolCapacityNoticeAlert` opts into proactive support and is the cheapest alert to provoke: its
# source only reads the pool capacity, so a single mocked `zpool.query_impl` raises and clears it.
ALERT_SOURCE = "ZpoolCapacity"
ALERT_CLASS = "ZpoolCapacityNotice"
ALERT_TEXT = f"Space usage for pool '{pool_name}' is 85%."

# Enabling Proactive Support requires a complete set of contact details, which the ticket body then
# quotes back.
SUPPORT_CONTACT = {
    "name": "Coverage Test",
    "title": "Coverage Test Engineer",
    "email": "coverage@ixsystems.com",
    "phone": "-",
    "secondary_name": "Coverage Test Secondary",
    "secondary_title": "Coverage Test Secondary Engineer",
    "secondary_email": "coverage-secondary@ixsystems.com",
    "secondary_phone": "-",
}

#: `support.new_ticket` runs on the server, so the payloads it is given are recorded there.
TICKETS_FILE = "/tmp/coverage_proactive_support_tickets"

RECORD_SUPPORT_TICKET = f"""\
    async def mock(self, job, data):
        import json
        with open("{TICKETS_FILE}", "a") as f:
            f.write(json.dumps(data.model_dump(mode="json")) + "\\n")

        return {{"ticket": 1, "url": None, "has_debug": False, "debug_attach_error": None}}
"""

FAILING_SUPPORT_TICKET = """\
    async def mock(self, job, data):
        raise Exception("Coverage test: the support proxy is unreachable")
"""


@pytest.fixture(autouse=True)
def no_stale_ticket_failures():
    """Alerts are persisted, so a ticket failure of an earlier run would leak into this one."""
    remove_oneshot_alerts("AutomaticAlertFailed")
    yield
    remove_oneshot_alerts("AutomaticAlertFailed")


@contextlib.contextmanager
def proactive_support(*, enabled):
    support = call("support.config")
    call("support.update", {**SUPPORT_CONTACT, "enabled": enabled})
    try:
        yield
    finally:
        # The contact details can only be cleared again while Proactive Support is off.
        call("support.update", {"enabled": False})
        call(
            "support.update",
            {
                **{field: support[field] for field in SUPPORT_CONTACT},
                "enabled": support["enabled"],
            },
        )


def almost_full_pool():
    """A `zpool.query_impl` result for a pool that is full enough to raise a capacity alert."""
    return {
        "name": pool_name,
        "guid": 0,
        "status": "ONLINE",
        "healthy": True,
        "warning": False,
        "status_code": "OK",
        "status_detail": None,
        "properties": {
            "capacity": {
                "value": 85,
                "raw": "85%",
                "source": "NONE",
            }
        },
        "topology": None,
        "scan": None,
        "expand": None,
        "features": None,
    }


def capacity_alerts():
    return [alert for alert in get_alerts_by_class(ALERT_CLASS) if alert["args"]["volume"] == pool_name]


def wait_for_capacity_alerts(present, attempts=6):
    """Run the capacity alert source until its alert has appeared (or disappeared) again."""
    for _ in range(attempts):
        # The source is only due every five minutes, so it has to be made due again by hand.
        call("alert.alert_source_clear_run", ALERT_SOURCE)
        run_alerts(fresh=True)
        if bool(alerts := capacity_alerts()) == present:
            return alerts

    raise AssertionError(f"The {ALERT_CLASS} alert did not {'appear' if present else 'disappear'}")


def standby_node_name():
    """The name `alert.list` gives to the alerts of the other controller."""
    return call("alert.node_map")["B" if call("failover.node") == "A" else "A"]


@contextlib.contextmanager
def almost_full_pool_on_standby():
    """Make the standby controller report a real `ZpoolCapacityNotice` alert."""
    assert capacity_alerts() == [], f"A {ALERT_CLASS} alert for {pool_name} is already present"

    with mock("zpool.query_impl", return_value=[almost_full_pool()], remote=True):
        alerts = wait_for_capacity_alerts(True)
        assert alerts[0]["node"] == standby_node_name()
        yield

    wait_for_capacity_alerts(False)


def forget_opened_tickets():
    ssh(f"rm -f {TICKETS_FILE}")


def opened_tickets():
    """The `support.new_ticket` payloads the mock recorded, oldest first."""
    return [json.loads(line) for line in ssh(f"cat {TICKETS_FILE} 2>/dev/null || true").splitlines() if line]


def one_line(text):
    """`html2text` wraps the alert text, so it can only be compared with the wrapping undone."""
    return " ".join(text.split())


def test_proactive_support_ticket_for_an_alert_from_the_standby_controller():
    forget_opened_tickets()

    with (
        proactive_support(enabled=True),
        mock("support.new_ticket", declaration=RECORD_SUPPORT_TICKET),
        almost_full_pool_on_standby(),
    ):
        (ticket,) = opened_tickets()

        assert ticket["title"] == f"Automatic alert ({call('system.dmidecode_info')['system-serial-number']})"
        assert ticket["category"] == "Hardware"
        assert ticket["criticality"] == "Loss of Functionality"
        assert ticket["environment"] == "Production"
        assert ticket["name"] == "Automatic Alert"
        assert ticket["email"] == "auto-support@truenas.com"
        assert ticket["phone"] == "-"
        assert ticket["attach_debug"] is False

        assert ticket["body"].startswith("The following new alerts appeared:")
        assert ALERT_TEXT in one_line(ticket["body"])
        # The support contact details are quoted back in every ticket.
        assert "Contact Name: Coverage Test" in ticket["body"]
        assert "Secondary Contact E-mail: coverage-secondary@ixsystems.com" in ticket["body"]

    # `ZpoolCapacityNoticeAlert` does not ask for its removal to be reported, so no second ticket is
    # opened once the alert is gone.
    assert len(opened_tickets()) == 1


def test_no_proactive_support_ticket_when_support_is_not_enabled():
    forget_opened_tickets()

    with (
        proactive_support(enabled=False),
        mock("support.new_ticket", declaration=RECORD_SUPPORT_TICKET),
        almost_full_pool_on_standby(),
    ):
        pass

    assert opened_tickets() == []


def test_no_proactive_support_ticket_for_a_class_that_opted_out():
    forget_opened_tickets()

    with (
        proactive_support(enabled=True),
        alert_classes({ALERT_CLASS: {"proactive_support": False}}),
        mock("support.new_ticket", declaration=RECORD_SUPPORT_TICKET),
        almost_full_pool_on_standby(),
    ):
        pass

    assert opened_tickets() == []


def test_failure_to_open_a_proactive_support_ticket_raises_an_alert():
    with (
        proactive_support(enabled=True),
        mock("support.new_ticket", declaration=FAILING_SUPPORT_TICKET),
        almost_full_pool_on_standby(),
    ):
        alerts = wait_for_alerts_by_class("AutomaticAlertFailed")
        assert alerts

        # The alert carries the ticket that could not be opened, and why it could not be opened.
        args = alerts[0]["args"]
        assert args["serial"] == call("system.dmidecode_info")["system-serial-number"]
        assert ALERT_TEXT in one_line(args["alert"])
        assert "Contact Name: Coverage Test" in args["alert"]
        assert "the support proxy is unreachable" in args["error"]
