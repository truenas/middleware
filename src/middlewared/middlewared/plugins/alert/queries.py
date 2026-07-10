from __future__ import annotations

from datetime import datetime
import errno
import time
from typing import Any
import uuid

from middlewared.alert.base import (
    Alert,
    AlertCategory,
    AlertClass,
    DismissableAlertClass,
    OneShotAlertClass,
    UnavailableException,
    alert_category_names,
)
from middlewared.api.current import (
    Alert as AlertListItem,
)
from middlewared.api.current import (
    AlertCategory as AlertCategoryListItem,
)
from middlewared.api.current import (
    AlertCategoryClass,
    AlertListCategoriesOptions,
)
from middlewared.service import ServiceContext
from middlewared.service_exception import CallError

from .runtime import (
    run_source as _run_source,
)
from .runtime import (
    send_alert_changed_event,
    send_alert_deleted_event,
)
from .serialize import AlertSerializer, get_alert_level, partition
from .state import FAILOVER_ALERTS_BACKOFF_SECS, POLICIES, AlertSourceLock, AlertState


def list_policies() -> list[str]:
    return POLICIES


def should_list_alert_class(alert_class: type[AlertClass], product_type: str, failover_licensed: bool) -> bool:
    if alert_class.config.category == AlertCategory.HA and not failover_licensed:
        return False

    return product_type in alert_class.config.products


async def list_categories(context: ServiceContext, options: AlertListCategoriesOptions) -> list[AlertCategoryListItem]:
    product_type = await context.call2(context.s.alert.product_type)
    failover_licensed: bool = await context.middleware.call("failover.licensed")

    classes: list[type[AlertClass]] = []
    for alert_class in AlertClass.classes:
        if not (
            options.include_all_products or
            should_list_alert_class(alert_class, product_type, failover_licensed)
        ):
            continue

        if not (options.include_hidden_classes or not alert_class.config.exclude_from_list):
            continue

        classes.append(alert_class)

    categories: list[AlertCategoryListItem] = []
    for category in AlertCategory:
        category_classes: list[AlertCategoryClass] = []
        for alert_class in classes:
            if alert_class.config.category != category:
                continue

            category_classes.append(
                AlertCategoryClass(
                    id=alert_class.config.name,
                    title=alert_class.config.title,
                    level=alert_class.config.level.name,
                    product_types=list(alert_class.config.products),  # type: ignore[arg-type]
                    proactive_support=alert_class.config.proactive_support,
                )
            )

        if not category_classes:
            continue

        category_classes.sort(key=lambda klass: klass.title)
        categories.append(
            AlertCategoryListItem(
                id=category.name,
                title=alert_category_names[category],
                classes=category_classes,
            )
        )

    return categories


async def list_alerts(context: ServiceContext, state: AlertState) -> list[AlertListItem]:
    as_ = AlertSerializer(context)
    classes = (await context.call2(context.s.alertclasses.config)).classes

    sorted_alerts = sorted(
        state.alerts,
        key=lambda alert: (
            -get_alert_level(alert, classes).value,
            alert.instance.config.title,
            alert.datetime,
        ),
    )

    result: list[AlertListItem] = []
    for alert in sorted_alerts:
        if await as_.should_show_alert(alert):
            result.append(await as_.serialize(alert))

    return result


def alert_by_uuid(state: AlertState, uuid: str) -> Alert[Any] | None:
    for alert in state.alerts:
        if alert.uuid == uuid:
            return alert

    return None


async def dismiss(context: ServiceContext, state: AlertState, uuid: str) -> None:
    alert = alert_by_uuid(state, uuid)
    if alert is None:
        return

    if isinstance(alert.instance, DismissableAlertClass):
        related_alerts, unrelated_alerts = partition(
            lambda a: (a.node, a.instance.config.name) == (alert.node, alert.instance.config.name),
            state.alerts,
        )
        left_alerts = await alert.instance.dismiss(context.middleware, related_alerts, alert)
        for deleted_alert in related_alerts:
            if deleted_alert not in left_alerts:
                delete_on_dismiss(context, state, deleted_alert)
    elif isinstance(alert.instance, OneShotAlertClass) and not alert.instance.config.deleted_automatically:
        delete_on_dismiss(context, state, alert)
    else:
        alert.dismissed = True
        await send_alert_changed_event(context, alert)


def delete_on_dismiss(context: ServiceContext, state: AlertState, alert: Alert[Any]) -> None:
    try:
        state.alerts.remove(alert)
        removed = True
    except ValueError:
        removed = False

    for policy in state.policies.values():
        policy.delete_alert(alert)

    if removed:
        send_alert_deleted_event(context, alert)


async def restore(context: ServiceContext, state: AlertState, uuid: str) -> None:
    alert = alert_by_uuid(state, uuid)
    if alert is None:
        return

    alert.dismissed = False

    await send_alert_changed_event(context, alert)


async def node_map(context: ServiceContext) -> dict[str, str]:
    nodes: dict[str, str] = {"A": "Controller A", "B": "Controller B"}
    if await context.middleware.call("failover.licensed"):
        node: str = await context.middleware.call("failover.node")
        status: str = await context.middleware.call("failover.status")
        if status == "MASTER":
            if node == "A":
                nodes = {"A": "Active Controller (A)", "B": "Standby Controller (B)"}
            else:
                nodes = {"A": "Standby Controller (A)", "B": "Active Controller (B)"}
        else:
            nodes[node] = f"{status.title()} Controller ({node})"

    return nodes


async def sources_stats(state: AlertState) -> dict[str, Any]:
    stats: dict[str, Any] = {}
    for name, runtimes in sorted(state.sources_run_times.items(), key=lambda t: t[0]):
        avg = runtimes["total_time"] / runtimes["total_count"] if runtimes["total_count"] != 0 else 0
        stats[name] = {"avg": avg, **runtimes}

    return stats


async def run_source(context: ServiceContext, state: AlertState, source_name: str) -> list[dict[str, Any]]:
    try:
        return [
            dict(alert.__dict__, instance=None, klass=alert.instance.config.name, args=alert.instance.args())
            for alert in await _run_source(context, state, source_name)
        ]
    except UnavailableException:
        raise CallError("This alert checker is unavailable", CallError.EALERTCHECKERUNAVAILABLE)


async def block_source(state: AlertState, source_name: str, timeout: int = 3600) -> str:
    if source_name not in state.alert_sources:
        raise CallError("Invalid alert source")

    lock = str(uuid.uuid4())
    state.blocked_sources[source_name].add(lock)
    state.sources_locks[lock] = AlertSourceLock(source_name, time.monotonic() + timeout)
    return lock


async def unblock_source(state: AlertState, lock: str) -> None:
    source_lock = state.sources_locks.pop(lock, None)
    if source_lock:
        state.blocked_sources[source_lock.source_name].remove(lock)


async def block_failover_alerts(state: AlertState) -> None:
    state.blocked_failover_alerts_until = time.monotonic() + FAILOVER_ALERTS_BACKOFF_SECS


def alert_source_clear_run(state: AlertState, name: str) -> None:
    alert_source = state.alert_sources.get(name)
    if not alert_source:
        raise CallError(f"Alert source {name!r} not found.", errno.ENOENT)

    state.alert_source_last_run[alert_source.name] = datetime.min


async def get_product_type(context: ServiceContext) -> str:
    return await context.middleware.call("system.product_type")  # type: ignore[no-any-return]
