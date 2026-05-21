from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from middlewared.alert.base import Alert, AlertCategory, AlertClass, AlertClassConfig, AlertLevel, AlertSource
from middlewared.alert.schedule import IntervalSchedule
from middlewared.plugins.update_.profile_ import UpdateProfiles


@dataclass(kw_only=True)
class CurrentlyRunningVersionDoesNotMatchProfileAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SYSTEM,
        level=AlertLevel.WARNING,
        title="Currently Running System Version Does Not Match Selected Update Profile",
        text=(
            "Currently running system version profile %(running)s does not match selected update profile %(selected)s."
        ),
    )

    running: str
    selected: str


class HasUpdateAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SYSTEM,
        level=AlertLevel.INFO,
        title="Update Available",
        text="A system update is available. Go to System → Update to download and apply the update.",
    )


def _profile_display_name(name: str) -> str:
    try:
        return UpdateProfiles[name].display_name
    except KeyError:
        return "<Unknown>"


class HasUpdateAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(hours=1))
    run_on_backup_node = False

    async def check(self) -> list[Alert[Any]] | Alert[Any] | None:
        try:
            update_status = await self.call2(self.s.update.status)
            if update_status.status:
                if not update_status.status.current_version.matches_profile:
                    config = await self.call2(self.s.update.config)

                    return Alert(CurrentlyRunningVersionDoesNotMatchProfileAlert(
                        running=_profile_display_name(update_status.status.current_version.profile),
                        selected=_profile_display_name(config.profile),
                    ))

                if update_status.status.new_version:
                    return Alert(HasUpdateAlert())
        except Exception:
            pass

        return None
