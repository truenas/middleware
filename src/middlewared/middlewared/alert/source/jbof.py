# Copyright (c) - iXsystems Inc.
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

import datetime

from middlewared.alert.base import Alert, AlertCategory, AlertClass, AlertLevel, AlertSource, SimpleOneShotAlertClass
from middlewared.alert.schedule import IntervalSchedule
from middlewared.plugins.enclosure_.enums import ElementStatus, ElementType


class JBOFTearDownFailureAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.WARNING
    title = "JBOF removal may require reboot"
    text = "Incomplete removal of JBOF requires a reboot to cleanup."

    async def delete(self, alerts, query):
        return []


class JBOFRedfishCommAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.CRITICAL
    title = 'Failed to Communicate with JBOF'
    text = 'JBOF: "%(desc)s" (%(ip1)s/%(ip2)s) Failed to communicate with redfish interface.'
    products = ('SCALE_ENTERPRISE',)


class JBOFInvalidDataAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.CRITICAL
    title = 'JBOF has invalid data'
    text = 'JBOF: "%(desc)s" (%(ip1)s/%(ip2)s) does not provide valid data for: %(keys)s'
    products = ('SCALE_ENTERPRISE',)


class JBOFElementWarningAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.WARNING
    title = 'JBOF element non-critical'
    text = 'JBOF: "%(desc)s" (%(ip1)s/%(ip2)s) %(etype)s %(key)s is noncritical: %(value)s'
    products = ('SCALE_ENTERPRISE',)


class JBOFElementCriticalAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.CRITICAL
    title = 'JBOF element critical'
    text = 'JBOF: "%(desc)s" (%(ip1)s/%(ip2)s) %(etype)s %(key)s is critical: %(value)s'
    products = ('SCALE_ENTERPRISE',)


class JBOFAlertSource(AlertSource):
    products = ('SCALE_ENTERPRISE',)
    run_on_backup_node = False
    schedule = IntervalSchedule(datetime.timedelta(minutes=5))

    def produce_alerts(self, jbof_config, jbof_data, alerts):
        for jbof in jbof_config:
            jbof_id_dict = {'desc': jbof['description'], 'ip1': jbof['mgmt_ip1'], 'ip2': jbof['mgmt_ip2']}
            data = None

            # First check that each configured JBOF has enclosure data returned.
            for _data in jbof_data:
                if jbof['uuid'] == _data['id']:
                    # Matched UUID
                    data = _data
                    break
            if data is None:
                # Did not find data for this JBOF
                alerts.append(Alert(JBOFRedfishCommAlertClass, jbof_id_dict))
                continue

            # Make sure the data seems to have the correct shape
            elements = data.get('elements')
            if not elements or not isinstance(elements, dict):
                alerts.append(Alert(JBOFInvalidDataAlertClass, {'keys': 'elements'} | jbof_id_dict))
                continue

            bad_keys = []
            for etype in ElementType:
                if edata := elements.get(etype.value):
                    if not isinstance(edata, dict):
                        bad_keys.append(etype.value)
                        continue
                    for key, v in edata.items():
                        match v['status']:
                            case ElementStatus.NONCRITICAL.value:
                                alerts.append(Alert(JBOFElementWarningAlertClass, {'etype': etype.value,
                                                                                   'key': key,
                                                                                   'value': v.get('value', '')
                                                                                   } | jbof_id_dict))
                            case ElementStatus.CRITICAL.value:
                                alerts.append(Alert(JBOFElementCriticalAlertClass, {'etype': etype.value,
                                                                                    'key': key,
                                                                                    'value': v.get('value', '')
                                                                                    } | jbof_id_dict))
                            case _:
                                pass
            if bad_keys:
                alerts.append(Alert(JBOFInvalidDataAlertClass, {'keys': ','.join(bad_keys)} | jbof_id_dict))

    async def check(self):
        alerts = []
        jbof_config = await self.middleware.call('jbof.query')

        if jbof_config:
            jbof_data = await self.middleware.call('enclosure2.map_jbof')
            self.produce_alerts(jbof_config, jbof_data, alerts)

        return alerts
