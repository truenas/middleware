# Copyright (c) 2017 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource


class IxAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = "iXsystems alert"
    text = "%s"

    products = ("ENTERPRISE",)


class IxAlertSource(AlertSource):
    products = ("ENTERPRISE",)
    run_on_backup_node = False

    async def check(self):
        support = await self.middleware.call('support.config')
        available = await self.middleware.call('support.is_available')
        if available and support['enabled'] is None:
            return Alert(
                IxAlertClass,
                'Proactive Support is not enabled. Please see the System/Proactive Support page.'
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
                    IxAlertClass,
                    'Please complete these fields on the System/Proactive Support page: %s.' % ', '.join(unfilled)
                )
