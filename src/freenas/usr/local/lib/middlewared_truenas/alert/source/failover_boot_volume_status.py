# Copyright (c) 2018 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

from middlewared.alert.base import Alert, AlertLevel, AlertSource


class FailoverBootVolumeStatusAlertSource(AlertSource):
    level = AlertLevel.CRITICAL
    title = "The boot volume state is not HEALTHY"

    async def check(self):
        alerts = []

        if not await self.middleware.call("notifier.failover_licensed"):
            return alerts

        try:
            state, status = tuple(await self.middleware.call('failover.call_remote', 'notifier.zpool_status',
                                                             ['freenas-boot']))
        except Exception as e:
            alerts.append(Alert(
                'Failed to check failover boot volume status with the other node: %s',
                args=[str(e)],
                level=AlertLevel.CRITICAL,
            ))
        else:
            if state == 'HEALTHY':
                pass
            else:
                alerts.append(Alert(
                    'The boot volume state is %(state)s: %(status)s',
                    args={
                        'state': state,
                        'status': status,
                    },
                    level=AlertLevel.CRITICAL,
                ))

        return alerts
