from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource


class ProactiveSupportAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = "Proactive Support Is Not Configured"
    text = "%s"

    products = ("SCALE_ENTERPRISE",)


class ProactiveSupportAlertSource(AlertSource):
    products = ("SCALE_ENTERPRISE",)
    run_on_backup_node = False

    async def check(self):
        support = await self.middleware.call('support.config')
        available = await self.middleware.call('support.is_available')
        if available and support['enabled'] is None:
            return Alert(
                ProactiveSupportAlertClass,
                'Proactive Support is not configured. Please see the System/Proactive Support page.'
            )

        if support['enabled']:
            # This is for people who had ix alert enabled before Proactive Support
            # feature and have not filled all the new fields.
            unfilled = []
            for name, verbose_name in await self.middleware.call('support.fields'):
                if not support[name]:
                    unfilled.append(verbose_name)

            if unfilled:
                return Alert(
                    ProactiveSupportAlertClass,
                    'Please complete these fields on the System/Proactive Support page: %s.' % ', '.join(unfilled)
                )
