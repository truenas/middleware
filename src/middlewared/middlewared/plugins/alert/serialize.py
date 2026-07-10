from __future__ import annotations

import typing
from typing import Any

from middlewared.alert.base import Alert, AlertLevel, OneShotAlertClass
from middlewared.api.current import Alert as AlertListItem
from middlewared.service import ServiceContext

from .state import DEFAULT_POLICY

if typing.TYPE_CHECKING:
    from collections.abc import Callable, Iterable


def get_alert_level(alert: Alert[Any], classes: dict[str, Any]) -> AlertLevel:
    return AlertLevel[classes.get(alert.instance.config.name, {}).get("level", alert.instance.config.level.name)]


def get_alert_policy(alert: Alert[Any], classes: dict[str, Any]) -> str:
    return classes.get(alert.instance.config.name, {}).get("policy", DEFAULT_POLICY)  # type: ignore[no-any-return]


def partition[T](predicate: Callable[[T], Any], iterable: Iterable[T]) -> tuple[list[T], list[T]]:
    """Split *iterable* into ``(matching, non_matching)`` lists by *predicate*.

    Order within each list is preserved from the input. The predicate is
    evaluated exactly once per item.
    """
    matching: list[T] = []
    non_matching: list[T] = []
    for item in iterable:
        if predicate(item):
            matching.append(item)
        else:
            non_matching.append(item)
    return matching, non_matching


class AlertSerializer:
    def __init__(self, context: ServiceContext) -> None:
        self.context = context

        self.initialized: bool = False
        self.product_type: str = ""
        self.classes: dict[str, dict[str, Any]] = {}
        self.nodes: dict[str, str] = {}

    async def serialize(self, alert: Alert[Any]) -> AlertListItem:
        await self._ensure_initialized()

        return AlertListItem(
            id=alert.uuid,
            uuid=alert.uuid,
            source=alert.source,
            klass=alert.instance.config.name,
            args=alert.instance.args(),
            node=self.nodes[alert.node],
            key=alert.key,
            datetime_=alert.datetime,
            last_occurrence=alert.last_occurrence,
            dismissed=alert.dismissed,
            mail=alert.mail,
            text=alert.text,
            level=self.classes.get(alert.instance.config.name, {}).get("level", alert.instance.config.level.name),
            formatted=alert.formatted,
            one_shot=isinstance(alert.instance, OneShotAlertClass) and not alert.instance.config.deleted_automatically,
        )

    async def get_alert_class(self, alert: Alert[Any]) -> dict[str, Any]:
        await self._ensure_initialized()
        return self.classes.get(alert.instance.config.name, {})

    async def should_show_alert(self, alert: Alert[Any]) -> bool:
        await self._ensure_initialized()

        if self.product_type not in alert.instance.config.products:
            return False

        if (await self.get_alert_class(alert)).get("policy") == "NEVER":
            return False

        return True

    async def _ensure_initialized(self) -> None:
        if not self.initialized:
            self.product_type = await self.context.call2(self.context.s.alert.product_type)
            self.classes = (await self.context.call2(self.context.s.alertclasses.config)).classes  # type: ignore[assignment]
            self.nodes = await self.context.call2(self.context.s.alert.node_map)

            self.initialized = True
