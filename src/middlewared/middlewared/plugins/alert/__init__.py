from __future__ import annotations

# `AlertService.list` shadows the builtin `list` within the class body, so annotations after it
# must qualify the type as `builtins.list` to refer to the type rather than the method.
import builtins
import typing
from typing import Any

from middlewared.alert.base import AlertSource, OneShotAlertClass
import middlewared.alert.source  # noqa: F401
from middlewared.api import Event, api_method
from middlewared.api.base import BaseModel
from middlewared.api.current import (
    AlertDismissArgs,
    AlertDismissResult,
    AlertListAddedEvent,
    AlertListArgs,
    AlertListCategoriesArgs,
    AlertListCategoriesResult,
    AlertListChangedEvent,
    AlertListPoliciesArgs,
    AlertListPoliciesResult,
    AlertListRemovedEvent,
    AlertListResult,
    AlertRestoreArgs,
    AlertRestoreResult,
)
from middlewared.service import Service, job, periodic, private

from . import lifecycle, oneshot, queries, runtime
from .state import AlertState

if typing.TYPE_CHECKING:
    from middlewared.main import Middleware


__all__ = ('AlertService',)


# Models for private `@api_method`s must live in the plugin (not `middlewared.api.*`); see check_model_module.
class AlertOneshotDeleteArgs(BaseModel):
    klass: str | list[str]
    query: Any = None


class AlertOneshotDeleteResult(BaseModel):
    result: None


class AlertService(Service):

    class Config:
        cli_namespace = "system.alert"
        events = [
            Event(
                name="alert.list",
                description="Sent on alert changes.",
                roles=["ALERT_LIST_READ"],
                models={
                    "ADDED": AlertListAddedEvent,
                    "CHANGED": AlertListChangedEvent,
                    "REMOVED": AlertListRemovedEvent,
                },
            ),
        ]

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)

        alert_sources: dict[str, AlertSource] = {
            name: cls(middleware) for name, cls in AlertSource.by_name.items()
        }
        self._state = AlertState(alert_sources=alert_sources)

    @api_method(AlertListPoliciesArgs, AlertListPoliciesResult, roles=['ALERT_LIST_READ'])
    async def list_policies(self) -> list[str]:
        """
        List all alert policies which indicate the frequency of the alerts.
        """
        return queries.list_policies()

    @api_method(AlertListCategoriesArgs, AlertListCategoriesResult, roles=['ALERT_LIST_READ'])
    async def list_categories(self, options: dict[str, Any]) -> list[dict[str, Any]]:
        """
        List all types of alerts which the system can issue.
        """
        return await queries.list_categories(self.context, options)

    @api_method(AlertListArgs, AlertListResult, roles=['ALERT_LIST_READ'])
    async def list(self) -> list[dict[str, Any]]:
        """
        List all types of alerts including active/dismissed currently in the system.
        """
        return await queries.list_alerts(self.context, self._state)

    @api_method(AlertDismissArgs, AlertDismissResult, roles=['ALERT_LIST_WRITE'])
    async def dismiss(self, uuid: str) -> None:
        """
        Dismiss `id` alert.
        """
        await queries.dismiss(self.context, self._state, uuid)

    @api_method(AlertRestoreArgs, AlertRestoreResult, roles=['ALERT_LIST_WRITE'])
    async def restore(self, uuid: str) -> None:
        """
        Restore `id` alert which had been dismissed.
        """
        await queries.restore(self.context, self._state, uuid)

    @private
    async def initialize(self, load: bool = True) -> None:
        await lifecycle.initialize(self.context, self._state, load)

    @private
    async def terminate(self) -> None:
        await lifecycle.terminate(self.context, self._state)

    @periodic(60)
    @private
    @job(lock="process_alerts", transient=True, lock_queue_size=1)
    async def process_alerts(self, job: Any) -> None:
        await runtime.process_alerts(self.context, self._state)

    @private
    @job(lock="process_alerts", transient=True)
    async def send_alerts(self, job: Any) -> None:
        await runtime.send_alerts(self.context, self._state)

    @periodic(3600, run_on_start=False)
    @private
    async def flush_alerts(self) -> None:
        await lifecycle.flush_alerts(self.context, self._state)

    @private
    @job(
        lock="process_alerts",
        lock_queue_size=None,  # Must be `None` so that alert operations are not discarded
        transient=True,
    )
    async def oneshot_create(self, job: Any, instance: OneShotAlertClass) -> None:
        """
        Creates a one-shot alert from the given alert class `instance`.

        Normal alert creation logic will be applied, so if you create an alert with the same `key` as an already
        existing alert, no duplicate alert will be created.

        :param instance: an instance of an `AlertClass` subclass that also inherits from `OneShotAlertClass`.
        """
        await oneshot.oneshot_create(self.context, self._state, instance)

    @api_method(AlertOneshotDeleteArgs, AlertOneshotDeleteResult, private=True)
    @job(
        lock="process_alerts",
        lock_queue_size=None,  # Must be `None` so that alert operations are not discarded
        transient=True,
    )
    async def oneshot_delete(self, job: Any, klass: str | builtins.list[str], query: Any = None) -> None:
        """
        Deletes one-shot alerts of specified `klass` or klasses, passing `query`
        to `klass.delete` method.

        It's not an error if no alerts matching delete `query` exist.

        :param klass: either one-shot alert class name (without the `AlertClass` suffix), or list thereof.
        :param query: `query` that will be passed to `klass.delete` method.
        """
        await oneshot.oneshot_delete(self.context, self._state, klass, query)

    @private
    async def run_source(self, source_name: str) -> builtins.list[dict[str, Any]]:
        return await queries.run_source(self.context, self._state, source_name)

    @private
    async def block_source(self, source_name: str, timeout: int = 3600) -> str:
        return await queries.block_source(self._state, source_name, timeout)

    @private
    async def unblock_source(self, lock: str) -> None:
        await queries.unblock_source(self._state, lock)

    @private
    async def block_failover_alerts(self) -> None:
        await queries.block_failover_alerts(self._state)

    @private
    def alert_source_clear_run(self, name: str) -> None:
        """
        Mark the alert source as never ran so that it will be re-run within the next minute.
        This is useful when you know some alert conditions were just changed.

        :param name: alert source name (without `AlertClass` suffix)
        """
        queries.alert_source_clear_run(self._state, name)

    @private
    async def sources_stats(self) -> dict[str, Any]:
        return await queries.sources_stats(self._state)

    @private
    async def node_map(self) -> dict[str, str]:
        return await queries.node_map(self.context)

    @private
    async def product_type(self) -> str:
        return await queries.product_type(self.context)


async def _event_system(middleware: Middleware, event_type: str, args: dict[str, Any]) -> None:
    if middleware.services.alert._state.send_alerts_on_ready:
        await middleware.call2(middleware.services.alert.send_alerts)


async def setup(middleware: Middleware) -> None:
    await middleware.call2(middleware.services.alertservice.initialize)

    await middleware.call2(middleware.services.alert.initialize)

    middleware.event_subscribe("system.ready", _event_system)
