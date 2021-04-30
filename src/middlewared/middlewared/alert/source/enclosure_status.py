# Copyright (c) 2015 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

import logging

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, AlertSource

logger = logging.getLogger(__name__)


class EnclosureUnhealthyAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.CRITICAL
    title = "Enclosure Status Is Not Healthy"
    text = "Enclosure %d (%s): %s is %s (%s)."

    products = ("ENTERPRISE",)


class EnclosureHealthyAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.INFO
    title = "Enclosure Status Is Healthy"
    text = "Enclosure %d (%s): is healthy."

    products = ("ENTERPRISE",)


class EnclosureStatusAlertSource(AlertSource):
    products = ("ENTERPRISE",)
    failover_related = True
    run_on_backup_node = False

    async def check(self):
        alerts = []

        for num, enc in enumerate(await self.middleware.call('enclosure.query')):
            healthy = True
            for ele in sum([e['elements'] for e in enc['elements']], []):
                if ele['status'] in ['Critical', 'Noncritical', 'Unrecoverable']:
                    pass
                elif ele['status'] == 'Not Installed' and ele['name'] in ['Power Supply']:
                    pass
                else:
                    continue

                # Enclosure element is CRITICAL in single head, ignore this for now
                # See #11918
                if ele['name'] == 'Enclosure':
                    continue

                # The 1.8V sensor is bugged on the echostream enclosure.  The
                # management chip loses it's mind and claims undervoltage, but
                # scoping this confirms the voltage is fine.
                # Ignore alerts from this element.
                # #10077
                if enc['name'] == 'ECStream 3U16+4R-4X6G.3 d10c':
                    if ele['descriptor'] == '1.8V Sensor':
                        continue

                healthy = False
                alerts.append(Alert(
                    EnclosureUnhealthyAlertClass,
                    args=[
                        num,
                        enc['name'],
                        f"{ele['name']} {hex(ele['slot'])} {ele['descriptor']}",
                        ele['status'],
                        ele['value_raw']
                    ],
                ))

            if healthy:
                alerts.append(Alert(
                    EnclosureHealthyAlertClass,
                    args=[num, enc['name']],
                ))

        return alerts
