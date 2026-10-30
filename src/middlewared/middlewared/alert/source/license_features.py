from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Self

from middlewared.alert.base import Alert, AlertCategory, AlertClassConfig, AlertLevel, OneShotAlertClass


@dataclass(kw_only=True)
class LicenseFeaturesAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SYSTEM,
        level=AlertLevel.WARNING,
        title="Licensed features in use without a license",
        text="%(lines)s",
    )

    lines: str

    @classmethod
    async def delete(cls, alerts: list[Alert[Self]], query: Any) -> list[Alert[Self]]:
        # keep only the alert whose text is `query`; None removes every alert of the class
        return [a for a in alerts if a.instance.lines == query]
