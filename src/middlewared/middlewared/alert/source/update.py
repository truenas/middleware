from datetime import timedelta

from middlewared.alert.base import Alert, AlertClass, AlertCategory, AlertLevel, AlertSource
from middlewared.alert.schedule import IntervalSchedule
from middlewared.plugins.update_.profile_ import UpdateProfiles


class CurrentlyRunningVersionDoesNotMatchProfileAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = "Currently Running System Version Does Not Match Selected Update Profile"
    text = (
        "Currently running system version profile %(running)s does not match selected update profile %(selected)s."
    )


class HasUpdateAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.INFO
    title = "Update Available"
    text = "A system update is available. Go to System → Update to download and apply the update."


def _profile_display_name(name: str) -> str:
    try:
        return UpdateProfiles[name].display_name
    except KeyError:
        return "<Unknown>"


class HasUpdateAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(hours=1))
    run_on_backup_node = False

    async def check(self) -> list[Alert] | Alert | None:
        try:
            update_status = await self.call2(self.s.update.status)
            if update_status.status:
                if not update_status.status.current_version.matches_profile:
                    config = await self.call2(self.s.update.config)

                    return Alert(CurrentlyRunningVersionDoesNotMatchProfileAlertClass, {
                        "running": _profile_display_name(update_status.status.current_version.profile),
                        "selected": _profile_display_name(config.profile),
                    })

                if update_status.status.new_version:
                    return Alert(HasUpdateAlertClass)
        except Exception:
            pass

        return None
