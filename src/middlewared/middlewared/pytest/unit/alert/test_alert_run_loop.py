"""What `__run_alerts` does to alerts that already exist when applicability changes.

Applicability is not only a filter over what is shown: a source that stops applying has the
alerts it persisted deleted, out of `self.alerts` and out of every policy. That is destructive
and irreversible, and nothing else in this tree reached it -- the whole enforcement block could
be removed and the suite stayed green.

The two ways a source can fail to run this tick are three lines apart in the source and mean
opposite things for state it already owns, so both are asserted here together.
"""

import pytest

from middlewared.alert.applicability import HA_LICENSED
from middlewared.plugins.alert import TestAlertClass as ANY_SYSTEM_CLASS
from middlewared.pytest.unit.alert.harness import (
    HA_LICENSED_FACTS,
    LICENSED,
    install_sources,
    make_runtime_service,
    make_source,
    seed_alert,
)
from middlewared.utils.time_utils import utc_now

# Distinct args, so each alert has its own key and two of them are never taken for one.
FIRST = {"which": "first"}
SECOND = {"which": "second"}


@pytest.mark.asyncio
async def test_run_purges_the_alerts_of_a_source_that_stopped_applying(monkeypatch):
    """The alerts of an excluded source are deleted; an admitted source keeps its own.

    Deletion has to reach the policies as well as the list. A policy that still remembers an
    alert reports it as gone on the next tick, and gone alerts are filtered by the class rule,
    which is deliberately wider than the source rule -- so an alert service would be told
    something was resolved when it had only stopped being checked.
    """
    runtime = make_runtime_service(monkeypatch, LICENSED)
    admitted, excluded = install_sources(
        monkeypatch,
        runtime,
        make_source("Admitted", produces=[(ANY_SYSTEM_CLASS, FIRST)]),
        make_source("Excluded", applies_to=HA_LICENSED, produces=[(ANY_SYSTEM_CLASS, SECOND)]),
    )
    runtime.set_alerts(
        seed_alert(ANY_SYSTEM_CLASS, FIRST, source="Admitted", uuid="admitted-uuid"),
        seed_alert(ANY_SYSTEM_CLASS, SECOND, source="Excluded", uuid="excluded-uuid"),
    )
    runtime.seed_policies()

    await runtime.run()

    assert [(alert.source, alert.uuid) for alert in runtime.alerts] == [("Admitted", "admitted-uuid")]
    assert all(policy.deleted == ["excluded-uuid"] for policy in runtime.policies.values())
    assert (admitted.checks, excluded.checks) == (1, 0)


@pytest.mark.asyncio
async def test_a_dismissed_alert_that_is_purged_comes_back_undismissed(monkeypatch):
    """What the purge costs when the facts that drove it were wrong.

    `get_license` answers `None` both for a system with no licence and for one whose licence
    daemon did not reply, so a daemon hiccup looks exactly like this sequence. The alert is not
    merely re-created: it comes back with a new uuid and no dismissal, which is a wave of alerts
    an operator had already dealt with.
    """
    runtime = make_runtime_service(monkeypatch, HA_LICENSED_FACTS)
    install_sources(
        monkeypatch,
        runtime,
        make_source("HaOnly", applies_to=HA_LICENSED, produces=[(ANY_SYSTEM_CLASS, FIRST)]),
    )

    await runtime.run()
    [alert] = runtime.alerts
    alert.dismissed = True
    dismissed_uuid = alert.uuid
    runtime.seed_policies()

    runtime.set_facts(LICENSED)
    await runtime.run()
    assert runtime.alerts == []

    runtime.set_facts(HA_LICENSED_FACTS)
    await runtime.run()

    [restored] = runtime.alerts
    assert restored.uuid != dismissed_uuid
    assert restored.dismissed is False

    gone_alerts, new_alerts = runtime.policies["IMMEDIATELY"].receive_alerts(utc_now(), runtime.alerts)
    assert [gone.uuid for gone in gone_alerts] == []
    assert [new.uuid for new in new_alerts] == [restored.uuid]


@pytest.mark.asyncio
async def test_a_gated_source_keeps_its_alerts_but_an_excluded_one_does_not(monkeypatch):
    """Not running because a gate closed and not running because the rule excludes it differ.

    A gate is a statement about this tick -- the peer is not worth asking, the blackout window is
    open -- and says nothing about whether the alerts already on file are still true. A rule
    saying the source is meaningless here does say that, which is why only one of the two throws
    the state away.
    """
    runtime = make_runtime_service(monkeypatch, LICENSED)
    gated, excluded = install_sources(
        monkeypatch,
        runtime,
        make_source("Gated", require_stable_peer=True, produces=[(ANY_SYSTEM_CLASS, FIRST)]),
        make_source("Excluded", applies_to=HA_LICENSED, produces=[(ANY_SYSTEM_CLASS, SECOND)]),
    )
    runtime.set_alerts(
        seed_alert(ANY_SYSTEM_CLASS, FIRST, source="Gated", uuid="gated-uuid"),
        seed_alert(ANY_SYSTEM_CLASS, SECOND, source="Excluded", uuid="excluded-uuid"),
    )
    runtime.seed_policies()

    await runtime.run()

    assert [(alert.source, alert.uuid) for alert in runtime.alerts] == [("Gated", "gated-uuid")]
    assert all(policy.deleted == ["excluded-uuid"] for policy in runtime.policies.values())
    assert (gated.checks, excluded.checks) == (0, 0)
