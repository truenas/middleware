from typing import Any

from middlewared.alert.base import (
    AlertCategory,
    AlertClassConfig,
    AlertLevel,
    NonDataclassAlertClass,
    OneShotAlertClass,
)


class DifFormattedAlert(NonDataclassAlertClass[str], OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.HARDWARE,
        level=AlertLevel.CRITICAL,
        title='Disk(s) Are Formatted With Data Integrity Feature (DIF).',
        text='Disk(s): %s are formatted with Data Integrity Feature (DIF) which is unsupported.',
        keys=[],
    )

    @classmethod
    def key_from_args(cls, args: Any) -> Any:
        return None
