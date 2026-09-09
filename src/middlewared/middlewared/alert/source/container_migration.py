from middlewared.alert.base import Alert, AlertCategory, AlertClass, AlertLevel, SimpleOneShotAlertClass

URL = "https://www.truenas.com/docs/scale/25.10/scaletutorials/containers/"


class LegacyVMInstancesNotMigratedAlertClass(AlertClass, SimpleOneShotAlertClass):
    keys = ["dataset"]
    deleted_automatically = False
    level = AlertLevel.WARNING
    category = AlertCategory.SYSTEM
    title = "Legacy VM Instances Were Not Migrated"
    text = (
        "Virtual machines created with the legacy Instances feature were not migrated and do not "
        "appear on the Virtual Machines screen: %(instances)s. Their storage is intact under "
        "%(dataset)s. See "
        f'<a href="{URL}" target="_blank">Containers</a> '
        "for how to recreate them on the Virtual Machines screen using the existing zvol."
    )

    # `key` is the dataset alone rather than the default (all of `args`), so a later run with a
    # different instance list replaces this alert instead of raising a second one beside it.
    async def create(self, args):
        return Alert(LegacyVMInstancesNotMigratedAlertClass, args, key=args["dataset"])
