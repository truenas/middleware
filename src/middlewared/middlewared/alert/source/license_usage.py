from datetime import timedelta
from typing import Any

from truenas_pylicensed import verify
from truenas_pylicensed.features import LicenseFeature

from middlewared.alert.base import (
    Alert,
    AlertCategory,
    AlertClass,
    AlertClassConfig,
    AlertLevel,
    AlertSource,
    NonDataclassAlertClass,
)
from middlewared.alert.schedule import IntervalSchedule
from middlewared.utils.entitlements import FEATURE_DISPLAY_NAMES
from middlewared.utils.license import DAEMON_ERRORS


class UnlicensedFeaturesInUseAlert(NonDataclassAlertClass[str], AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SYSTEM,
        level=AlertLevel.WARNING,
        title="Unlicensed Features Are In Use",
        text="%s",
    )

    @classmethod
    def key_from_args(cls, args: Any) -> None:
        # The text changes as features are cleaned up one by one, and each change must not re-notify.
        return None


class UnlicensedFeaturesInUseAlertSource(AlertSource):
    run_on_backup_node = False
    schedule = IntervalSchedule(timedelta(minutes=10))

    async def check(self) -> list[Alert[Any]]:
        # An unreachable daemon reads as "nothing is licensed", which would list every configured feature.
        if (await self.middleware.run_in_thread(verify)).code in DAEMON_ERRORS:
            return []

        usage = await self.middleware.call("truenas.entitlements.usage")
        lines = [
            f"{FEATURE_DISPLAY_NAMES[key]}: {entry['message']}"
            for key, entry in usage.items()
            # HA's "use" is the hardware itself, which nobody can remove.
            if key != LicenseFeature.HA and not entry["entitled"] and entry["in_use"]
        ]
        lines.extend(await self.middleware.call("truenas.license.revoke_pending"))
        if not lines:
            return []

        return [Alert(UnlicensedFeaturesInUseAlert("\n".join(lines)))]
