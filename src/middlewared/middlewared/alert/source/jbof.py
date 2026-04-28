# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from dataclasses import dataclass
import datetime
from typing import Any

from middlewared.alert.base import (
    Alert,
    AlertCategory,
    AlertClass,
    AlertClassConfig,
    AlertLevel,
    AlertSource,
    OneShotAlertClass,
)
from middlewared.alert.schedule import IntervalSchedule
from middlewared.plugins.enclosure_.enums import ElementStatus, ElementType
from middlewared.utils import ProductType


class JBOFTearDownFailureAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.HARDWARE,
        level=AlertLevel.WARNING,
        title="JBOF removal may require reboot",
        text="Incomplete removal of JBOF requires a reboot to cleanup.",
        keys=[],
    )


@dataclass(kw_only=True)
class JBOFRedfishCommAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.HARDWARE,
        level=AlertLevel.CRITICAL,
        title='Failed to Communicate with JBOF',
        text='JBOF: "%(desc)s" (%(ip1)s/%(ip2)s) Failed to communicate with redfish interface.',
        products=(ProductType.ENTERPRISE,),
    )

    desc: str
    ip1: str
    ip2: str


@dataclass(kw_only=True)
class JBOFInvalidDataAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.HARDWARE,
        level=AlertLevel.CRITICAL,
        title='JBOF has invalid data',
        text='JBOF: "%(desc)s" (%(ip1)s/%(ip2)s) does not provide valid data for: %(keys)s',
        products=(ProductType.ENTERPRISE,),
    )

    desc: str
    ip1: str
    ip2: str
    keys: str


@dataclass(kw_only=True)
class JBOFElementWarningAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.HARDWARE,
        level=AlertLevel.WARNING,
        title='JBOF element non-critical',
        text='JBOF: "%(desc)s" (%(ip1)s/%(ip2)s) %(etype)s %(key)s is noncritical: %(value)s',
        products=(ProductType.ENTERPRISE,),
    )

    desc: str
    ip1: str
    ip2: str
    etype: str
    key: str
    value: str


@dataclass(kw_only=True)
class JBOFElementCriticalAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.HARDWARE,
        level=AlertLevel.CRITICAL,
        title='JBOF element critical',
        text='JBOF: "%(desc)s" (%(ip1)s/%(ip2)s) %(etype)s %(key)s is critical: %(value)s',
        products=(ProductType.ENTERPRISE,),
    )

    desc: str
    ip1: str
    ip2: str
    etype: str
    key: str
    value: str


class JBOFAlertSource(AlertSource):
    products = (ProductType.ENTERPRISE,)
    run_on_backup_node = False
    schedule = IntervalSchedule(datetime.timedelta(minutes=5))

    def produce_alerts(
        self, jbof_config: list[dict[str, Any]], jbof_data: list[dict[str, Any]], alerts: list[Alert[Any]],
    ) -> None:
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
                alerts.append(Alert(JBOFRedfishCommAlert(**jbof_id_dict)))
                continue

            # Make sure the data seems to have the correct shape
            elements = data.get('elements')
            if not elements or not isinstance(elements, dict):
                alerts.append(Alert(JBOFInvalidDataAlert(keys='elements', **jbof_id_dict)))
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
                                alerts.append(Alert(JBOFElementWarningAlert(
                                    etype=etype.value,
                                    key=key,
                                    value=v.get('value', ''),
                                    **jbof_id_dict,
                                )))
                            case ElementStatus.CRITICAL.value:
                                alerts.append(Alert(JBOFElementCriticalAlert(
                                    etype=etype.value,
                                    key=key,
                                    value=v.get('value', ''),
                                    **jbof_id_dict,
                                )))
                            case _:
                                pass
            if bad_keys:
                alerts.append(Alert(JBOFInvalidDataAlert(keys=','.join(bad_keys), **jbof_id_dict)))

    async def check(self) -> list[Alert[Any]]:
        alerts: list[Alert[Any]] = []
        jbof_config = await self.middleware.call('jbof.query')

        if jbof_config:
            jbof_data = await self.middleware.call('enclosure2.map_jbof')
            self.produce_alerts(jbof_config, jbof_data, alerts)

        return alerts
