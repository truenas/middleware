from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, OneShotAlertClass


class WebUiRootLoginAlertClass(AlertClass, OneShotAlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = "Root User Can Still Log In To The Web UI"
    text = (
        "Root user has their password disabled, but as there are no other users granted with a privilege of Local "
        "Administrator, they can still log in to the Web UI. Please create a separate user for the administrative "
        "purposes in order to forbid root from logging in to the Web UI."
    )

    exclude_from_list = True

    async def create(self, args):
        return Alert(self.__class__, args)

    async def delete(self, alerts, query):
        return []
