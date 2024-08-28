# Copyright (c) - iXsystems Inc.
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

import time

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource, UnavailableException


class FailoverRemoteSystemInaccessibleAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = 'Other Controller is Inaccessible'
    text = 'Other TrueNAS controller is inaccessible. Contact support.'
    products = ('SCALE_ENTERPRISE',)
    proactive_support = True
    proactive_support_notify_gone = True


class FailoverRemoteSystemInaccessibleAlertSource(AlertSource):
    products = ('SCALE_ENTERPRISE',)
    failover_related = True
    run_on_backup_node = False

    def __init__(self, middleware):
        super().__init__(middleware)
        self.last_available = time.monotonic()

    async def check(self):
        try:
            await self.middleware.call('failover.call_remote', 'core.ping', {'timeout': 2})
        except Exception:
            if time.monotonic() - self.last_available > 4 * 3600:
                return [Alert(FailoverRemoteSystemInaccessibleAlertClass)]
            else:
                raise UnavailableException()

        self.last_available = time.monotonic()
        return []
