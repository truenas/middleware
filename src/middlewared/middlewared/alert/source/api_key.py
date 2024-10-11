import json

from middlewared.alert.base import Alert, AlertClass, SimpleOneShotAlertClass, AlertCategory, AlertLevel


class ApiKeyRevokedAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = "API Key Revoked"
    text = (
        "%(key_name)s: API key has been revoked and must either be renewed or deleted. "
        "Once the maintenance is complete, API client configuration must be updated to "
        "use the renwed API key."
    )

    async def create(self, args):
        return Alert(ApiKeyRevokedAlertClass, args, key=args['key_name'])

    async def delete(self, alerts, key_name_set):
        remaining = []
        for alert in alerts:
            if json.loads(alert.key) not in key_name_set:
                continue

            remaining.append(alert)

        return remaining
