# Copyright (c) 2015 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

import logging

from freenasUI.truenas import ses

from middlewared.alert.base import Alert, AlertLevel, AlertSource

logger = logging.getLogger(__name__)


class EnclosureStatusAlertSource(AlertSource):
    level = AlertLevel.CRITICAL
    title = "Enclosure status is critical"

    run_on_backup_node = False

    async def check(self):
        encs = ses.Enclosures()
        alerts = []

        for enc in encs:
            healthy = True
            for ele in enc:
                if ele.status == 'Unrecoverable':
                    status = 'UNRECOVERABLE'
                elif ele.status == 'Critical':
                    if ele.name == 'Enclosure' and not (
                        await self.middleware.call("datastore.query", "failover.failover")
                    ):
                        continue
                    status = 'CRITICAL'
                elif ele.status == 'Unrecoverable':
                    status = 'UNRECOVERABLE'
                elif ele.status == 'Noncritical':
                    status = 'UNRECOVERABLE'
                else:
                    continue

                # Enclosure element is CRITICAL in single head, ignore this for now
                # See #11918
                if ele.name == 'Enclosure':
                    continue

                # The 1.8V sensor is bugged on the echostream enclosure.  The
                # management chip loses it's mind and claims undervoltage, but
                # scoping this confirms the voltage is fine.
                # Ignore alerts from this element.
                # #10077
                if enc.name == 'ECStream 3U16+4R-4X6G.3 d10c':
                    if ele.descriptor == '1.8V Sensor':
                        continue

                healthy = False
                alerts.append(Alert(
                    'Enclosure %d (%s), %s is %s',
                    args=[enc.num, enc.encname, ele.name, status],
                    level=AlertLevel.CRITICAL,
                ))
                # Log the element, see #10187
                logger.warning(
                    'Element %s: %s, status: %s (%s), descriptor: %s',
                    hex(ele.slot),
                    ele.name,
                    ele.status,
                    hex(ele.value_raw),
                    ele.descriptor,
                )

            if healthy:
                alerts.append(Alert(
                    'Enclosure %d (%s) is HEALTHY',
                    args=[enc.num, enc.encname],
                    level=AlertLevel.INFO,
                ))

        return alerts
