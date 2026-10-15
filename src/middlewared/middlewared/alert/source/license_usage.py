from typing import Any

from middlewared.alert.base import (
    AlertCategory,
    AlertClassConfig,
    AlertLevel,
    NonDataclassAlertClass,
    OneShotAlertClass,
)


class UnlicensedFeaturesInUseAlert(NonDataclassAlertClass[str], OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SYSTEM,
        level=AlertLevel.WARNING,
        title="Unlicensed Features Are In Use",
        text="%s",
        deleted_automatically=False,
        keys=[],
    )

    @classmethod
    def key_from_args(cls, args: Any) -> None:
        # The text changes as features are cleaned up one by one, and each change must not re-notify.
        return None
