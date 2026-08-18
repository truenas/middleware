from __future__ import annotations

import typing
from typing import Any, TypeAlias

from middlewared.alert.base import Alert, AlertLevel, OneShotAlertClass
from middlewared.api.current import Alert as AlertListItem
from middlewared.api.current import AlertClassConfiguration
from middlewared.service import ServiceContext

from .state import DEFAULT_POLICY

if typing.TYPE_CHECKING:
    from collections.abc import Callable, Iterable

AlertClasses: TypeAlias = dict[str, AlertClassConfiguration]


def get_alert_level(alert: Alert[Any], classes: AlertClasses) -> AlertLevel:
    if (config := classes.get(alert.instance.config.name)) is not None and "level" in config.model_fields_set:
        return AlertLevel[config.level]

    level: AlertLevel = alert.instance.config.level
    return level


def get_alert_policy(alert: Alert[Any], classes: AlertClasses) -> str:
    if (config := classes.get(alert.instance.config.name)) is not None and "policy" in config.model_fields_set:
        return config.policy

    return DEFAULT_POLICY


def get_alert_proactive_support(alert: Alert[Any], classes: AlertClasses) -> bool:
    if (
        (config := classes.get(alert.instance.config.name)) is not None
        and "proactive_support" in config.model_fields_set
    ):
        return config.proactive_support

    return True


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
        self.classes: AlertClasses = {}
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
            level=get_alert_level(alert, self.classes).name,
            formatted=alert.formatted,
            one_shot=isinstance(alert.instance, OneShotAlertClass) and not alert.instance.config.deleted_automatically,
        )

    async def proactive_support(self, alert: Alert[Any]) -> bool:
        await self._ensure_initialized()
        return get_alert_proactive_support(alert, self.classes)

    async def should_show_alert(self, alert: Alert[Any]) -> bool:
        await self._ensure_initialized()

        if self.product_type not in alert.instance.config.products:
            return False

        if get_alert_policy(alert, self.classes) == "NEVER":
            return False

        return True

    async def _ensure_initialized(self) -> None:
        if not self.initialized:
            self.product_type = await self.context.call2(self.context.s.alert.product_type)
            self.classes = (await self.context.call2(self.context.s.alertclasses.config)).classes
            self.nodes = await self.context.call2(self.context.s.alert.node_map)

            self.initialized = True
