# Copyright (c) 2017 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

from middlewared.alert.base import Alert, AlertLevel, AlertSource


class IxAlertSource(AlertSource):
    level = AlertLevel.WARNING
    title = 'The Proactive Support feature is not enabled.'

    async def check(self):
        support = await self.middleware.call('support.config')
        available = await self.middleware.call('support.is_available')
        if available and support['enabled'] is None:
            return Alert('The Proactive Support feature is not enabled. Please see the System -> Proactive Support tab.')
        if support['enabled']:
            # This is for people who had ix alert enabled before Proactive Support
            # feature and have not filled all the new fields.
            unfilled = []
            for name, verbose_name in await self.middleware.call('support.fields'):
                if not support[name]:
                    unfilled.append(verbose_name)
            if unfilled:
                return Alert('Please fill in these fields on the System -> Proactive Support tab: %s.',
                             args=[', '.join(unfilled)])
