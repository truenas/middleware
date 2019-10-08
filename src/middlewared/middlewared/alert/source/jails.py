from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, OneShotAlertClass, Alert


class PluginUpdateAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False

    category = AlertCategory.PLUGINS
    level = AlertLevel.INFO
    title = 'Plugin Update Available'
    text = 'An update is available for the "%(name)s" plugin.'

    async def create(self, args):
        return Alert(PluginUpdateAlertClass, args, key=args['name'])

    async def delete(self, alerts, query):
        return list(filter(
            lambda alert: alert.key != str(query),
            alerts
        ))
