from datetime import timedelta

from middlewared.alert.base import Alert, AlertClass, AlertCategory, AlertLevel, AlertSource
from middlewared.alert.schedule import IntervalSchedule


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


class HasUpdateAlertSource(AlertSource):
    schedule = IntervalSchedule(timedelta(hours=1))
    run_on_backup_node = False

    async def check(self) -> list[Alert] | Alert | None:
        try:
            update_status = await self.call2(self.s.update.status)
            if update_status.status:
                if not update_status.status.current_version.matches_profile:
                    config = await self.call2(self.s.update.config)
                    profile_choices = await self.call2(self.s.update.profile_choices)

                    if running_profile := profile_choices.get(update_status.status.current_version.profile):
                        running = running_profile.name
                    else:
                        running = "<Unknown>"

                    if selected_profile := profile_choices.get(config.profile):
                        selected = selected_profile.name
                    else:
                        selected = "<Unknown>"

                    return Alert(CurrentlyRunningVersionDoesNotMatchProfileAlertClass, {
                        "running": running,
                        "selected": selected,
                    })

                if update_status.status.new_version:
                    return Alert(HasUpdateAlertClass)
        except Exception:
            pass

        return None
