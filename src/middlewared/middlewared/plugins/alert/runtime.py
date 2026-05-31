from __future__ import annotations

import copy
from datetime import timezone
from itertools import zip_longest
import time
from typing import Any
import uuid

import html2text
from truenas_api_client.exc import ReserveFDException

from middlewared.alert.base import (
    Alert,
    AlertClass,
    AlertLevel,
    OneShotAlertClass,
    UnavailableException,
)
from middlewared.alert.base import (
    AlertService as _AlertService,
)
from middlewared.plugins.failover_.remote import NETWORK_ERRORS
from middlewared.service import ServiceContext
from middlewared.service_exception import CallError, NetworkActivityDisabled
from middlewared.utils.time_utils import utc_now

from .alert_classes import (
    AlertSourceRunFailedAlert,
    AlertSourceRunFailedOnBackupNodeAlert,
    AutomaticAlertFailedAlert,
)
from .serialize import AlertSerializer, get_alert_level, get_alert_policy
from .state import FAILOVER_ALERTS_BACKOFF_SECS, AlertFailoverInfo, AlertState


async def process_alerts(context: ServiceContext, state: AlertState) -> None:
    if not await should_run_or_send_alerts(context):
        return

    valid_alerts = copy.deepcopy(state.alerts)
    await run_alerts(context, state)

    expire_alerts(state)

    if not await should_run_or_send_alerts(context):
        state.alerts = valid_alerts
        return

    await context.call2(context.s.alert.send_alerts)


async def send_alerts(context: ServiceContext, state: AlertState) -> None:
    if await context.middleware.call("system.state") != "READY":
        state.send_alerts_on_ready = True
        return

    product_type: str = await context.call2(context.s.alert.product_type)
    classes: dict[str, Any] = (await context.call2(context.s.alertclasses.config)).classes

    now = utc_now()
    for policy_name, policy in state.policies.items():
        gone_alerts, new_alerts = policy.receive_alerts(now, state.alerts)

        for alert_service_desc in await context.call2(context.s.alertservice.query, [["enabled", "=", True]]):
            service_level = AlertLevel[alert_service_desc.level]

            service_alerts = [
                alert
                for alert in state.alerts
                if (
                    product_type in alert.instance.config.products
                    and get_alert_level(alert, classes).value >= service_level.value
                    and get_alert_policy(alert, classes) != "NEVER"
                )
            ]
            service_gone_alerts = [
                alert
                for alert in gone_alerts
                if (
                    product_type in alert.instance.config.products
                    and get_alert_level(alert, classes).value >= service_level.value
                    and get_alert_policy(alert, classes) == policy_name
                )
            ]
            service_new_alerts = [
                alert
                for alert in new_alerts
                if (
                    product_type in alert.instance.config.products
                    and get_alert_level(alert, classes).value >= service_level.value
                    and get_alert_policy(alert, classes) == policy_name
                )
            ]
            for gone_alert in list(service_gone_alerts):
                for new_alert in service_new_alerts:
                    if (
                        gone_alert.instance.config.name == new_alert.instance.config.name
                        and gone_alert.key == new_alert.key
                    ):
                        service_gone_alerts.remove(gone_alert)
                        service_new_alerts.remove(new_alert)
                        break

            if not service_gone_alerts and not service_new_alerts:
                continue

            factory = _AlertService.by_name[alert_service_desc.attributes.type]
            alert_service = factory(
                context.middleware,
                alert_service_desc.attributes.model_dump(context={"expose_secrets": True}),
            )

            alerts = [alert for alert in service_alerts if not alert.dismissed]
            service_gone_alerts = [alert for alert in service_gone_alerts if not alert.dismissed]
            service_new_alerts = [alert for alert in service_new_alerts if not alert.dismissed]

            if alerts or service_gone_alerts or service_new_alerts:
                try:
                    await alert_service.send(alerts, service_gone_alerts, service_new_alerts)
                except Exception:
                    context.logger.error(
                        "Error in alert service %r",
                        alert_service_desc.attributes.type,
                        exc_info=True,
                    )

        if policy_name == "IMMEDIATELY":
            as_ = AlertSerializer(context)
            for alert in gone_alerts:
                if await as_.should_show_alert(alert):
                    send_alert_deleted_event(context, alert)
            for alert in new_alerts:
                if await as_.should_show_alert(alert):
                    context.middleware.send_event(
                        "alert.list",
                        "ADDED",
                        id=alert.uuid,
                        fields=await as_.serialize(alert),
                    )

            for alert in new_alerts:
                if alert.mail:
                    try:
                        await context.call2(context.s.mail.send, alert.mail)
                    except NetworkActivityDisabled:
                        pass

            if await context.middleware.call("system.is_enterprise"):
                gone_proactive_support_alerts = [
                    alert
                    for alert in gone_alerts
                    if (
                        alert.instance.config.proactive_support
                        and (await as_.get_alert_class(alert)).get("proactive_support", True)
                        and alert.instance.config.proactive_support_notify_gone
                    )
                ]
                new_proactive_support_alerts = [
                    alert
                    for alert in new_alerts
                    if (
                        alert.instance.config.proactive_support
                        and (await as_.get_alert_class(alert)).get("proactive_support", True)
                    )
                ]
                if gone_proactive_support_alerts or new_proactive_support_alerts:
                    if await context.middleware.call("support.is_available_and_enabled"):
                        support = await context.middleware.call("support.config")

                        msg: list[str] = []
                        if gone_proactive_support_alerts:
                            msg.append("The following alerts were cleared:")
                            msg += [
                                f"* {html2text.html2text(alert.formatted)}" for alert in gone_proactive_support_alerts
                            ]
                        if new_proactive_support_alerts:
                            msg.append("The following new alerts appeared:")
                            msg += [
                                f"* {html2text.html2text(alert.formatted)}" for alert in new_proactive_support_alerts
                            ]

                        serial: str = (await context.middleware.call("system.dmidecode_info"))["system-serial-number"]

                        for name, verbose_name in await context.middleware.call("support.fields"):
                            value = support[name]
                            if value:
                                msg += ["", "{}: {}".format(verbose_name, value)]

                        msg_str: str = "\n".join(msg)

                        job = await context.middleware.call(
                            "support.new_ticket",
                            {
                                "title": "Automatic alert (%s)" % serial,
                                "body": msg_str,
                                "attach_debug": False,
                                "category": "Hardware",
                                "criticality": "Loss of Functionality",
                                "environment": "Production",
                                "name": "Automatic Alert",
                                "email": "auto-support@truenas.com",
                                "phone": "-",
                            },
                        )
                        await job.wait()
                        if job.error:
                            await context.call2(
                                context.s.alert.oneshot_create,
                                AutomaticAlertFailedAlert(serial=serial, alert=msg_str, error=str(job.error)),
                            )


async def should_run_or_send_alerts(context: ServiceContext) -> bool:
    if await context.middleware.call("system.state") != "READY":
        return False

    if await context.middleware.call("failover.licensed"):
        status: str = await context.middleware.call("failover.status")
        if status == "BACKUP" or await context.middleware.call("failover.in_progress"):
            return False

    return True


async def get_failover_info(context: ServiceContext, state: AlertState) -> AlertFailoverInfo:
    this_node, other_node = "A", "B"
    run_on_backup_node = False
    run_failover_related = await context.middleware.call("failover.licensed")
    if run_failover_related:
        if await context.middleware.call("failover.node") != "A":
            this_node, other_node = "B", "A"

        run_failover_related = time.monotonic() > state.blocked_failover_alerts_until
        if run_failover_related:
            args: tuple[list[Any], dict[str, Any]] = ([], {"connect_timeout": 2})

            # Do not run on backup if there is a software version mismatch
            try:
                rem_ver = await context.middleware.call("failover.call_remote", "system.version", *args)
                run_on_backup_node = (await context.middleware.call("system.version")) == rem_ver
            except Exception:
                pass

            # Do not run on backup if the other node is not READY
            if run_on_backup_node:
                try:
                    run_on_backup_node = (
                        await context.middleware.call("failover.call_remote", "system.state", *args)
                    ) == "READY"
                except Exception:
                    pass

            # Do not run on backup if the other node is not BACKUP
            if run_on_backup_node:
                try:
                    run_on_backup_node = (
                        await context.middleware.call("failover.call_remote", "system.status", *args)
                    ) == "BACKUP"
                except Exception:
                    pass

            if run_on_backup_node:
                # If BACKUP node is in good shape, check whether it
                # has been booted for long enough.
                try:
                    run_on_backup_node = (
                        await context.middleware.call("failover.call_remote", "system.time_info", *args)
                    )["uptime_seconds"] > FAILOVER_ALERTS_BACKOFF_SECS
                except Exception:
                    pass

    return AlertFailoverInfo(
        this_node=this_node,
        other_node=other_node,
        run_on_backup_node=run_on_backup_node,
        run_failover_related=run_failover_related,
    )


async def handle_locked_alert_source(
    context: ServiceContext,
    state: AlertState,
    name: str,
    this_node: str,
    other_node: str,
) -> tuple[list[Alert[Any]], list[Alert[Any]], set[str]]:
    this_node_alerts: list[Alert[Any]] = []
    other_node_alerts: list[Alert[Any]] = []
    locked = state.blocked_sources[name]
    if locked:
        context.logger.debug("Not running alert source %r because it is blocked", name)
        for i in filter(lambda x: x.source == name, state.alerts):
            if i.node == this_node:
                this_node_alerts.append(i)
            elif i.node == other_node:
                other_node_alerts.append(i)
    return this_node_alerts, other_node_alerts, locked


async def run_other_node_alert_source(context: ServiceContext, name: str) -> list[Alert[Any]]:
    keys = ("datetime", "last_occurrence", "dismissed", "mail")
    other_node_alerts: list[Alert[Any]] = []
    try:
        try:
            for alert in await context.middleware.call("failover.call_remote", "alert.run_source", [name]):
                klass = AlertClass.by_name[alert["klass"]]
                instance = klass.from_args(alert["args"])
                other_node_alerts.append(
                    Alert(
                        instance,
                        **{k: v for k, v in alert.items() if k in keys},
                        _source=alert["source"],
                        _key=alert["key"],
                    )
                )
        except CallError as e:
            if e.errno not in NETWORK_ERRORS + (CallError.EALERTCHECKERUNAVAILABLE,):
                raise
    except ReserveFDException:
        context.logger.debug("Failed to reserve a privileged port")
    except Exception as e:
        other_node_alerts = [
            Alert(AlertSourceRunFailedOnBackupNodeAlert(source_name=name, traceback=str(e)), _source=name)
        ]

    return other_node_alerts


async def run_alerts(context: ServiceContext, state: AlertState) -> None:
    product_type: str = await context.call2(context.s.alert.product_type)
    fi = await get_failover_info(context, state)
    for k, source_lock in list(state.sources_locks.items()):
        if source_lock.expires_at <= time.monotonic():
            await context.call2(context.s.alert.unblock_source, k)

    for alert_source in state.alert_sources.values():
        if product_type not in alert_source.products:
            continue

        if alert_source.failover_related and not fi.run_failover_related:
            continue

        if alert_source.require_stable_peer and not fi.run_on_backup_node:
            continue

        if not alert_source.schedule.should_run(utc_now(), state.alert_source_last_run[alert_source.name]):
            continue

        state.alert_source_last_run[alert_source.name] = utc_now()

        this_node_alerts, other_node_alerts, locked = await handle_locked_alert_source(
            context, state, alert_source.name, fi.this_node, fi.other_node
        )
        if not locked:
            context.logger.trace("Running alert source: %r", alert_source.name)  # type: ignore[attr-defined]
            try:
                this_node_alerts = await run_source(context, state, alert_source.name)
            except UnavailableException:
                pass

            if fi.run_on_backup_node and alert_source.run_on_backup_node:
                other_node_alerts = await run_other_node_alert_source(context, alert_source.name)

        for talert, oalert in zip_longest(this_node_alerts, other_node_alerts, fillvalue=None):
            if talert is not None:
                talert.node = fi.this_node
                handle_alert(state, talert)
            if oalert is not None:
                oalert.node = fi.other_node
                handle_alert(state, oalert)

        state.alerts = [a for a in state.alerts if a.source != alert_source.name] + this_node_alerts + other_node_alerts


def handle_alert(state: AlertState, alert: Alert[Any]) -> None:
    try:
        existing_alert = [
            a
            for a in state.alerts
            if (a.node, a.source, a.instance.config.name, a.key)
            == (alert.node, alert.source, alert.instance.config.name, alert.key)
        ][0]
    except IndexError:
        existing_alert = None

    if existing_alert is None:
        alert.uuid = str(uuid.uuid4())
    else:
        alert.uuid = existing_alert.uuid
    if existing_alert is None:
        alert.datetime = alert.datetime or utc_now()
        if alert.datetime.tzinfo is not None:
            alert.datetime = alert.datetime.astimezone(timezone.utc).replace(tzinfo=None)
    else:
        alert.datetime = existing_alert.datetime
    alert.last_occurrence = utc_now()
    if existing_alert is None:
        alert.dismissed = False
    else:
        alert.dismissed = existing_alert.dismissed


def expire_alerts(state: AlertState) -> None:
    state.alerts = list(filter(lambda alert: not should_expire_alert(alert), state.alerts))


def should_expire_alert(alert: Alert[Any]) -> bool:
    if isinstance(alert.instance, OneShotAlertClass):
        if alert.instance.config.expires_after is not None:
            return alert.last_occurrence < utc_now() - alert.instance.config.expires_after  # type: ignore[operator]

    return False


async def run_source(context: ServiceContext, state: AlertState, source_name: str) -> list[Alert[Any]]:
    alert_source = state.alert_sources[source_name]

    start = time.monotonic()
    try:
        alerts = (await alert_source.check()) or []
    except UnavailableException:
        raise
    except Exception as e:
        if source_name not in state.alert_sources_errors:
            context.logger.error("Error checking for alert %r", alert_source.name, exc_info=True)
            state.alert_sources_errors.add(source_name)

        alerts = [
            Alert(
                AlertSourceRunFailedAlert(
                    source_name=alert_source.name,
                    traceback=str(e),
                )
            )
        ]
    else:
        state.alert_sources_errors.discard(source_name)
        if not isinstance(alerts, list):
            alerts = [alerts]
    finally:
        run_time = time.monotonic() - start
        source_stat = state.sources_run_times[source_name]
        source_stat["last"] = source_stat["last"][-9:] + [run_time]
        source_stat["max"] = max(source_stat["max"], run_time)
        source_stat["total_count"] += 1
        source_stat["total_time"] += run_time

    keys: set[str] = set()
    unique_alerts: list[Alert[Any]] = []
    for alert in alerts:
        if alert.key in keys:
            continue

        keys.add(alert.key)
        unique_alerts.append(alert)
    alerts = unique_alerts

    for alert in alerts:
        alert.source = source_name

    return alerts


async def send_alert_changed_event(context: ServiceContext, alert: Alert[Any]) -> None:
    as_ = AlertSerializer(context)
    if await as_.should_show_alert(alert):
        context.middleware.send_event("alert.list", "CHANGED", id=alert.uuid, fields=await as_.serialize(alert))


def send_alert_deleted_event(context: ServiceContext, alert: Alert[Any]) -> None:
    context.middleware.send_event("alert.list", "REMOVED", id=alert.uuid)
