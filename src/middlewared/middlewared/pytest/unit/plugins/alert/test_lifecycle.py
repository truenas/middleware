from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from functools import partial
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from middlewared.alert.base import Alert, AlertCategory, AlertClass, AlertClassConfig, AlertLevel, OneShotAlertClass
from middlewared.plugins.alert import lifecycle
from middlewared.plugins.alert.alert_classes import AlertModel
from middlewared.plugins.alert.state import AlertState
from middlewared.pytest.unit.datastore_harness import datastore_test
from middlewared.service import ServiceContext


@dataclass(kw_only=True)
class LifecycleTestAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SYSTEM,
        level=AlertLevel.WARNING,
        title="Lifecycle test",
        text="Lifecycle test %(name)s",
    )

    name: str


#: Records the alerts every `LifecycleTestOneShotAlert.load` call was given.
ONE_SHOT_LOADS: list[list[str]] = []


@dataclass(kw_only=True)
class LifecycleTestOneShotAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SYSTEM,
        level=AlertLevel.WARNING,
        title="Lifecycle test one-shot",
        text="Lifecycle test one-shot %(name)s",
    )

    name: str

    @classmethod
    async def load(cls, middleware, alerts):
        ONE_SHOT_LOADS.append([alert.instance.name for alert in alerts])
        return [alert for alert in alerts if alert.instance.name != "obsolete"]


@dataclass(kw_only=True)
class LifecycleTestFailingLoadAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SYSTEM,
        level=AlertLevel.WARNING,
        title="Lifecycle test failing load",
        text="Lifecycle test failing load %(name)s",
    )

    name: str

    @classmethod
    async def load(cls, middleware, alerts):
        raise Exception("The resource this alert refers to can no longer be queried")


def alert_row(**changes):
    """A `system.alert` row as `alert.flush_alerts` would have written it."""
    return {
        "node": "A",
        "source": "",
        "key": '{"name": "first"}',
        "datetime": datetime(2020, 1, 1, 0, 0),
        "last_occurrence": datetime(2020, 1, 2, 0, 0),
        "text": "Lifecycle test %(name)s",
        "args": {"name": "first"},
        "dismissed": False,
        "uuid": "uuid-1",
        "klass": "LifecycleTest",
        **changes,
    }


@asynccontextmanager
async def lifecycle_test(**mocked_calls):
    calls = {
        "system.is_enterprise": AsyncMock(return_value=False),
        "failover.node": AsyncMock(return_value="A"),
        "failover.licensed": AsyncMock(return_value=False),
        "failover.status": AsyncMock(return_value="MASTER"),
    }
    calls.update(mocked_calls)

    async with datastore_test(calls, models=(AlertModel,)) as ds:
        middleware = ds.middleware
        # `TestSource` is the only alert source this system knows about.
        state = AlertState({"TestSource": Mock()})
        context = ServiceContext(middleware, logging.getLogger("middlewared.plugins.alert"))
        # `alert.flush_alerts` is called via the service container, which is a `Mock` here.
        middleware.services.alert.flush_alerts = partial(lifecycle.flush_alerts, context, state)

        async def store(*rows):
            for row in rows:
                await ds.insert("system.alert", row)

        async def stored():
            return [{k: v for k, v in row.items() if k != "id"} for row in await ds.query("system.alert")]

        yield SimpleNamespace(
            ds=ds, middleware=middleware, state=state, context=context, calls=calls, store=store, stored=stored
        )


def alert_names(alerts):
    return [alert.instance.name for alert in alerts]


# ---------------------------------------------------------------------------
# initialize: loading the stored alerts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_initialize_loads_a_stored_alert():
    async with lifecycle_test() as t:
        await t.store(alert_row(source="TestSource"))

        await lifecycle.initialize(t.context, t.state)

        (alert,) = t.state.alerts
        assert isinstance(alert.instance, LifecycleTestAlert)
        assert alert.instance.name == "first"
        assert alert.uuid == "uuid-1"
        assert alert.source == "TestSource"
        assert alert.key == '{"name": "first"}'
        assert alert.node == "A"
        assert alert.dismissed is False
        assert alert.datetime == datetime(2020, 1, 1, 0, 0)
        assert alert.last_occurrence == datetime(2020, 1, 2, 0, 0)
        assert alert.formatted == "Lifecycle test first"


@pytest.mark.asyncio
async def test_initialize_replaces_the_previously_loaded_alerts():
    async with lifecycle_test() as t:
        t.state.alerts = [Alert(LifecycleTestAlert(name="stale"), _uuid="uuid-stale")]
        await t.store(alert_row())

        await lifecycle.initialize(t.context, t.state)

        assert alert_names(t.state.alerts) == ["first"]


@pytest.mark.asyncio
async def test_initialize_discards_an_alert_of_a_source_that_is_gone(caplog):
    async with lifecycle_test() as t:
        await t.store(
            alert_row(uuid="uuid-gone", source="SourceThatNoLongerExists", args={"name": "gone"}),
            alert_row(source="TestSource"),
        )

        with caplog.at_level(logging.INFO):
            await lifecycle.initialize(t.context, t.state)

        assert alert_names(t.state.alerts) == ["first"]
        assert "Alert source 'SourceThatNoLongerExists' is no longer present" in caplog.text


@pytest.mark.asyncio
async def test_initialize_discards_an_alert_of_a_class_that_is_gone(caplog):
    async with lifecycle_test() as t:
        await t.store(
            alert_row(uuid="uuid-gone", klass="ClassThatNoLongerExists", args={"name": "gone"}),
            alert_row(),
        )

        with caplog.at_level(logging.INFO):
            await lifecycle.initialize(t.context, t.state)

        assert alert_names(t.state.alerts) == ["first"]
        assert "Alert class 'ClassThatNoLongerExists' is no longer present" in caplog.text


@pytest.mark.asyncio
async def test_initialize_discards_an_alert_whose_args_no_longer_match_its_class(caplog):
    async with lifecycle_test() as t:
        await t.store(
            alert_row(uuid="uuid-gone", args={"argument_that_no_longer_exists": 1}),
            alert_row(),
        )

        with caplog.at_level(logging.INFO):
            await lifecycle.initialize(t.context, t.state)

        assert alert_names(t.state.alerts) == ["first"]
        assert "Error loading alert class 'LifecycleTest'" in caplog.text


@pytest.mark.asyncio
async def test_initialize_deduplicates_alerts_by_uuid():
    async with lifecycle_test() as t:
        await t.store(alert_row(), alert_row(args={"name": "duplicate"}, key='{"name": "duplicate"}'))

        await lifecycle.initialize(t.context, t.state)

        # The first row wins, the one that was stored twice is not loaded again.
        assert alert_names(t.state.alerts) == ["first"]


@pytest.mark.asyncio
async def test_initialize_lets_one_shot_alert_classes_drop_obsolete_alerts():
    async with lifecycle_test() as t:
        ONE_SHOT_LOADS.clear()
        await t.store(
            alert_row(uuid="uuid-1", klass="LifecycleTestOneShot", args={"name": "still here"}),
            alert_row(uuid="uuid-2", klass="LifecycleTestOneShot", args={"name": "obsolete"}),
            alert_row(uuid="uuid-3"),
        )

        await lifecycle.initialize(t.context, t.state)

        assert alert_names(t.state.alerts) == ["still here", "first"]
        # `load` is called once per class, with every alert of that class.
        assert ONE_SHOT_LOADS == [["still here", "obsolete"]]


@pytest.mark.asyncio
async def test_initialize_discards_one_shot_alerts_whose_load_fails(caplog):
    async with lifecycle_test() as t:
        await t.store(
            alert_row(uuid="uuid-1", klass="LifecycleTestFailingLoad", args={"name": "unloadable"}),
            alert_row(uuid="uuid-2"),
        )

        with caplog.at_level(logging.INFO):
            await lifecycle.initialize(t.context, t.state)

        # Only the alerts of the class that could not be loaded are lost.
        assert alert_names(t.state.alerts) == ["first"]
        assert "Error loading one-shot alert" in caplog.text


@pytest.mark.asyncio
async def test_initialize_without_load_discards_the_stored_alerts():
    async with lifecycle_test() as t:
        t.state.alerts = [Alert(LifecycleTestAlert(name="in memory"), _uuid="uuid-memory")]
        await t.store(alert_row())

        await lifecycle.initialize(t.context, t.state, False)

        assert t.state.alerts == []
        # The in-memory alerts are dropped before being flushed, so the database ends up empty, too.
        assert await t.stored() == []


# ---------------------------------------------------------------------------
# initialize: the rest of the state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("node", ["A", "B"])
async def test_initialize_takes_the_node_from_failover_on_enterprise(node):
    async with lifecycle_test(
        **{"system.is_enterprise": AsyncMock(return_value=True), "failover.node": AsyncMock(return_value=node)}
    ) as t:
        t.state.node = "this will be overwritten"

        await lifecycle.initialize(t.context, t.state)

        assert t.state.node == node


@pytest.mark.asyncio
async def test_initialize_does_not_ask_failover_for_the_node_on_community_edition():
    async with lifecycle_test() as t:
        t.state.node = "B"

        await lifecycle.initialize(t.context, t.state)

        assert t.state.node == "A"
        t.calls["failover.node"].assert_not_called()


@pytest.mark.asyncio
async def test_initialize_makes_every_alert_source_due_again():
    async with lifecycle_test() as t:
        t.state.alert_source_last_run["TestSource"] = datetime(2030, 1, 1, 0, 0)

        await lifecycle.initialize(t.context, t.state)

        assert t.state.alert_source_last_run["TestSource"] == datetime.min
        assert t.state.alert_source_last_run["AnySourceAtAll"] == datetime.min


@pytest.mark.asyncio
async def test_initialize_seeds_the_policies_with_the_loaded_alerts():
    async with lifecycle_test() as t:
        await t.store(alert_row())

        await lifecycle.initialize(t.context, t.state)

        assert set(t.state.policies) == {"IMMEDIATELY", "HOURLY", "DAILY", "NEVER"}

        # The loaded alerts are not reported as new: they were already there before the restart.
        later = datetime(2030, 1, 1, 12, 0)
        for name, policy in t.state.policies.items():
            assert policy.receive_alerts(later, t.state.alerts) == ([], []), name


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "policy_name,same_batch,next_batch",
    [
        ("IMMEDIATELY", datetime(2030, 1, 1, 12, 0), datetime(2030, 1, 1, 12, 0, 1)),
        ("HOURLY", datetime(2030, 1, 1, 12, 30), datetime(2030, 1, 1, 13, 0)),
        ("DAILY", datetime(2030, 1, 1, 23, 0), datetime(2030, 1, 2, 0, 0)),
    ],
)
async def test_initialize_creates_the_policies_with_their_own_schedules(policy_name, same_batch, next_batch):
    async with lifecycle_test() as t:
        await lifecycle.initialize(t.context, t.state)
        policy = t.state.policies[policy_name]
        policy.receive_alerts(datetime(2030, 1, 1, 12, 0), [])

        new_alert = Alert(LifecycleTestAlert(name="new"), _uuid="uuid-new")

        # Within the same batch the alert is held back...
        assert policy.receive_alerts(same_batch, [new_alert]) == ([], [])
        # ...and it is reported once the next one begins.
        assert policy.receive_alerts(next_batch, [new_alert]) == ([], [new_alert])


@pytest.mark.asyncio
async def test_initialize_creates_a_never_policy_that_reports_nothing():
    async with lifecycle_test() as t:
        await lifecycle.initialize(t.context, t.state)
        policy = t.state.policies["NEVER"]

        new_alert = Alert(LifecycleTestAlert(name="new"), _uuid="uuid-new")

        assert policy.receive_alerts(datetime(2030, 1, 1, 12, 0), [new_alert]) == ([], [])
        assert policy.receive_alerts(datetime(2031, 1, 1, 12, 0), [new_alert]) == ([], [])


# ---------------------------------------------------------------------------
# flush_alerts / terminate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flush_alerts_replaces_the_stored_alerts():
    async with lifecycle_test() as t:
        await t.store(alert_row(uuid="uuid-stale", args={"name": "stale"}))
        t.state.alerts = [
            Alert(
                LifecycleTestAlert(name="first"),
                datetime=datetime(2020, 1, 1, 0, 0),
                last_occurrence=datetime(2020, 1, 2, 0, 0),
                node="A",
                dismissed=False,
                # `mail` is not a column of `system.alert` and must not be stored.
                mail={"subject": "Lifecycle test", "text": "Lifecycle test", "to": ["alerts@ixsystems.com"]},
                _uuid="uuid-1",
                _source="TestSource",
            )
        ]

        await lifecycle.flush_alerts(t.context, t.state)

        assert await t.stored() == [alert_row(source="TestSource")]


@pytest.mark.asyncio
async def test_flush_alerts_stores_nothing_when_there_are_no_alerts():
    async with lifecycle_test() as t:
        await t.store(alert_row())

        await lifecycle.flush_alerts(t.context, t.state)

        assert await t.stored() == []


@pytest.mark.asyncio
async def test_flush_alerts_does_not_ask_for_the_failover_status_without_a_license():
    async with lifecycle_test() as t:
        await lifecycle.flush_alerts(t.context, t.state)

        t.calls["failover.status"].assert_not_called()


@pytest.mark.asyncio
async def test_flush_alerts_is_skipped_on_the_standby_node():
    async with lifecycle_test(
        **{"failover.licensed": AsyncMock(return_value=True), "failover.status": AsyncMock(return_value="BACKUP")}
    ) as t:
        await t.store(alert_row())

        await lifecycle.flush_alerts(t.context, t.state)

        # The standby node must not touch the alerts the active node stored.
        assert await t.stored() == [alert_row()]


@pytest.mark.asyncio
async def test_flush_alerts_runs_on_the_active_node():
    async with lifecycle_test(
        **{"failover.licensed": AsyncMock(return_value=True), "failover.status": AsyncMock(return_value="MASTER")}
    ) as t:
        await t.store(alert_row())

        await lifecycle.flush_alerts(t.context, t.state)

        assert await t.stored() == []


@pytest.mark.asyncio
async def test_terminate_flushes_the_alerts():
    async with lifecycle_test() as t:
        t.state.alerts = [
            Alert(
                LifecycleTestAlert(name="first"),
                datetime=datetime(2020, 1, 1, 0, 0),
                last_occurrence=datetime(2020, 1, 2, 0, 0),
                node="A",
                dismissed=False,
                _uuid="uuid-1",
                _source="",
            )
        ]

        await lifecycle.terminate(t.context, t.state)

        assert await t.stored() == [alert_row()]
