from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from middlewared.alert.base import Alert, AlertClass, OneShotAlertClass
from middlewared.service import ServiceContext
from middlewared.utils.time_utils import utc_now

from .state import AlertPolicy, AlertState


async def initialize(context: ServiceContext, state: AlertState, load: bool = True) -> None:
    is_enterprise: bool = await context.middleware.call("system.is_enterprise")

    state.node = "A"
    if is_enterprise:
        if await context.middleware.call("failover.node") == "B":
            state.node = "B"

    state.alerts = []
    if load:
        alerts_uuids: set[str] = set()
        alerts_by_classes: defaultdict[str, list[Alert[Any]]] = defaultdict(list)
        for alert in await context.middleware.call("datastore.query", "system.alert"):
            del alert["id"]

            if alert["source"] and alert["source"] not in state.alert_sources:
                context.logger.info("Alert source %r is no longer present", alert["source"])
                continue

            class_name: str = alert.pop("klass")
            try:
                klass = AlertClass.by_name[class_name]
            except KeyError:
                context.logger.info("Alert class %r is no longer present", class_name)
                continue

            alert["_uuid"] = alert.pop("uuid")
            alert["_source"] = alert.pop("source")
            alert["_key"] = alert.pop("key")
            alert["_text"] = alert.pop("text")

            args = alert.pop("args")
            try:
                instance = klass.from_args(args)
                alert = Alert(instance, **alert)
            except Exception as e:
                context.logger.info("Error loading alert class %r: %r", class_name, e)
                continue

            if alert.uuid not in alerts_uuids:
                alerts_uuids.add(alert.uuid)
                alerts_by_classes[alert.instance.config.name].append(alert)

        for alerts in alerts_by_classes.values():
            if isinstance(alerts[0].instance, OneShotAlertClass):
                try:
                    alerts = await alerts[0].instance.load(context.middleware, alerts)
                except Exception as e:
                    context.logger.info("Error loading one-shot alert %r: %r", alerts[0].instance, e)
                    continue

            state.alerts.extend(alerts)
    else:
        await context.call2(context.s.alert.flush_alerts)

    state.alert_source_last_run = defaultdict(lambda: datetime.min)

    state.policies = {
        "IMMEDIATELY": AlertPolicy(),
        "HOURLY": AlertPolicy(lambda d: (d.date(), d.hour)),
        "DAILY": AlertPolicy(lambda d: d.date()),
        "NEVER": AlertPolicy(lambda d: None),
    }
    for policy in state.policies.values():
        policy.receive_alerts(utc_now(), state.alerts)


async def terminate(context: ServiceContext, state: AlertState) -> None:
    await context.call2(context.s.alert.flush_alerts)


async def flush_alerts(context: ServiceContext, state: AlertState) -> None:
    if await context.middleware.call("failover.licensed"):
        if await context.middleware.call("failover.status") == "BACKUP":
            return

    await context.middleware.call("datastore.delete", "system.alert", [])

    for alert in state.alerts:
        d = alert.__dict__.copy()
        d["klass"] = alert.instance.config.name
        d["args"] = alert.instance.args()
        del d["instance"]
        del d["mail"]
        await context.middleware.call("datastore.insert", "system.alert", d)
