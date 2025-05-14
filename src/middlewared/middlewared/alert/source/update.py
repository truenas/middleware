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

    async def check(self):
        try:
            update_status = await self.middleware.call("update.status")
            if update_status["status"]:
                if not update_status["status"]["current_train"]["matches_profile"]:
                    config = await self.middleware.call("update.config")
                    profile_choices = await self.middleware.call("update.profile_choices")
                    return Alert(CurrentlyRunningVersionDoesNotMatchProfileAlertClass, {
                        "running": (
                            profile_choices.get(update_status["status"]["current_train"]["profile"], {}).
                            get("name", "<Unknown>")
                        ),
                        "selected": profile_choices.get(config["profile"], {}).get("name", "<Unknown>"),
                    })

                if update_status["status"]["new_version"]:
                    return Alert(HasUpdateAlertClass)
        except Exception:
            pass
