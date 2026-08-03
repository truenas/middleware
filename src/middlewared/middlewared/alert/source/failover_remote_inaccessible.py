# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

import time

from middlewared.alert.applicability import APPLIANCE_OR_HA_LICENSED, HA_LICENSED
from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource, UnavailableException
from middlewared.utils.crypto import generate_token


class FailoverRemoteSystemInaccessibleAlertClass(AlertClass):
    category = AlertCategory.HA
    level = AlertLevel.CRITICAL
    title = 'Other Controller is Inaccessible'
    text = 'Other TrueNAS controller is inaccessible. Contact support. Incident ID: %s.'
    applies_to = APPLIANCE_OR_HA_LICENSED
    listed_only_when = HA_LICENSED
    proactive_support = True
    proactive_support_notify_gone = True


class FailoverRemoteSystemInaccessibleAlertSource(AlertSource):
    applies_to = HA_LICENSED
    post_failover_blackout = True
    run_on_backup_node = False

    def __init__(self, middleware):
        super().__init__(middleware)
        self.last_available = time.monotonic()
        self.incident_id = None

    async def check(self):
        try:
            await self.middleware.call('failover.call_remote', 'core.ping', [], {'timeout': 2})
        except Exception:
            if time.monotonic() - self.last_available > 4 * 3600:
                if self.incident_id is None:
                    self.incident_id = generate_token(16, url_safe=True)
                return [Alert(FailoverRemoteSystemInaccessibleAlertClass, args=[self.incident_id])]
            else:
                raise UnavailableException()

        self.last_available = time.monotonic()
        self.incident_id = None
        return []
