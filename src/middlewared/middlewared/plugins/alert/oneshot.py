from __future__ import annotations

from typing import Any

from middlewared.alert.base import Alert, AlertClass, OneShotAlertClass
from middlewared.service import ServiceContext
from middlewared.service_exception import CallError

from .runtime import handle_alert
from .serialize import partition
from .state import AlertState


async def oneshot_create(context: ServiceContext, state: AlertState, instance: OneShotAlertClass) -> None:
    if not isinstance(instance, OneShotAlertClass):
        raise CallError(f"Alert {instance!r} is not a one-shot alert class")

    alert = Alert(instance)
    alert.source = ""
    alert.node = state.node

    handle_alert(state, alert)

    state.alerts = [a for a in state.alerts if a.uuid != alert.uuid] + [alert]

    await context.call2(context.s.alert.send_alerts)


async def oneshot_delete(context: ServiceContext, state: AlertState, klass: str | list[str], query: Any = None) -> None:
    klasses: list[str]
    if isinstance(klass, list):
        klasses = klass
    else:
        klasses = [klass]

    deleted = False
    for klassname in klasses:
        try:
            klass_type = AlertClass.by_name[klassname]
        except KeyError:
            raise CallError(f"Invalid alert source: {klassname!r}")

        if not issubclass(klass_type, OneShotAlertClass):
            raise CallError(f"Alert class {klassname!r} is not a one-shot alert class")

        related_alerts, unrelated_alerts = partition(
            lambda a: (a.node, a.instance.config.name) == (state.node, klass_type.config.name), state.alerts
        )
        left_alerts = await klass_type.delete(related_alerts, query)
        for deleted_alert in related_alerts:
            if deleted_alert not in left_alerts:
                state.alerts.remove(deleted_alert)
                deleted = True

    if deleted:
        # We need to flush alerts to the database immediately after deleting oneshot alerts.
        # Some oneshot alerts can only de deleted programmatically (i.e. cloud sync oneshot alerts are deleted
        # when deleting cloud sync task). If we delete a cloud sync task and then reboot the system abruptly,
        # the alerts won't be flushed to the database and on next boot an alert for nonexisting cloud sync task
        # will appear, and it won't be deletable.
        await context.call2(context.s.alert.flush_alerts)

        await context.call2(context.s.alert.send_alerts)
