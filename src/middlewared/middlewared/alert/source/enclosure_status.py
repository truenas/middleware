# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions
from dataclasses import dataclass
from middlewared.utils import ProductType

from middlewared.alert.base import (
    AlertClass,
    AlertCategory,
    AlertLevel,
    Alert,
    AlertSource,
)


@dataclass(slots=True, frozen=True, kw_only=True)
class BadElement:
    enc_name: str
    descriptor: str
    status: str
    value: str
    value_raw: int
    enc_title: str

    def args(self):
        return [self.enc_name, self.descriptor, self.status, self.value, self.value_raw]


class EnclosureUnhealthyAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.CRITICAL
    title = "Enclosure Status Is Not Healthy"
    text = 'Enclosure (%s): Element "%s" is reporting a status of "%s" with a value of "%s". (raw value "%s")'
    products = (ProductType.ENTERPRISE,)


class EnclosureHealthyAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.INFO
    title = "Enclosure Status Is Healthy"
    text = "Enclosure (%s) is healthy."
    products = (ProductType.ENTERPRISE,)


class EnclosureStatusAlertSource(AlertSource):
    products = (ProductType.ENTERPRISE,)
    failover_related = True
    run_on_backup_node = False
    bad = ("critical", "noncritical", "unknown", "unrecoverable")
    bad_elements: list | list[tuple[BadElement, int]] = list()

    async def should_report(self, ele_type: str, ele_value: dict[str], **extra):
        """We only want to raise an alert for an element's status
        if it meets a certain criteria"""
        if not ele_value["value"]:
            # if we don't have an actual value, doesn't
            # matter what status the element is reporting
            # we'll skip it so we don't raise alarm to
            # end-user unnecessarily
            return False
        elif ele_value["status"].lower() not in self.bad:
            return False
        elif ele_type == "Current Sensor" and isinstance(raw := ele_value["value_raw"], int):
            byte2 = (raw >> 16) & 0xff
            # Some enclosures (e.g. HGST H4060-J) assert "Fail on" on a current
            # rail when drives draw no current on it. This is a false positive
            # caused by 12V-primary drives (e.g. Kioxia PM7) that legitimately
            # draw 0A on the 5V rail. Suppress if zero current and "Fail on" is
            # asserted, but no over-threshold bits (Warn over, Crit over) are set.
            if (
                (raw & 0xffff) == 0
                and (byte2 & 0x40)
                and not (byte2 & 0x0a)
                and self._zero_fail_other_rail_is_healthy(ele_value["descriptor"], extra["sensors"])
            ):
                return False

        return True

    @staticmethod
    def _is_voltage_suffix(s: str) -> bool:
        """Return True if s looks like a voltage designator (e.g. '5V', '12V', '3.3V')."""
        return len(s) >= 2 and s[0].isdigit() and s[-1] == 'V'

    @staticmethod
    def _zero_fail_other_rail_is_healthy(descriptor: str, current_sensors: dict) -> bool:
        """Return True if another current sensor for the same component on a different
        voltage rail shows healthy current, indicating the component is powered.

        For example, "CURR IOM A 5V" and "CURR IOM A 12V" monitor the same IOM on
        different voltage rails. If the 12V rail shows positive current with no
        Fail bit, the IOM is powered and the 5V zero reading is benign.

        Both descriptors must end with a voltage designator (e.g. "5V", "12V") and
        share the same prefix. This prevents false matches between descriptors like
        "CURR PSU A IN" and "CURR PSU A OUT", which are different measurement points
        on the same PSU rather than different voltage rails on the same component.
        """
        parts = descriptor.rsplit(maxsplit=1)
        if len(parts) != 2 or not EnclosureStatusAlertSource._is_voltage_suffix(parts[1]):
            return False
        base = parts[0]
        for sibling in current_sensors.values():
            sibling_desc = sibling.get('descriptor') or ''
            if sibling_desc == descriptor:
                continue
            sibling_parts = sibling_desc.rsplit(maxsplit=1)
            if (
                len(sibling_parts) != 2
                or sibling_parts[0] != base
                or not EnclosureStatusAlertSource._is_voltage_suffix(sibling_parts[1])
            ):
                continue
            raw = sibling.get('value_raw')
            if not isinstance(raw, int):
                continue
            # Healthy: draws current and no Fail bit
            if (raw & 0xffff) > 0 and not ((raw >> 16) & 0x40):
                return True
        return False

    async def check(self):
        good_enclosures, bad_elements = [], []
        for enc in await self.middleware.call("enclosure2.query"):
            enc_title = f"{enc['name']} (id: {enc['id']})"
            good_enclosures.append([enc_title])
            enc["elements"].pop("Array Device Slot")  # dont care about disk slots
            current_sensors = enc["elements"].get("Current Sensor", {})  # used for edge case in should_report
            for element_type, element_values in enc["elements"].items():
                for ele_value in element_values.values():
                    if await self.should_report(element_type, ele_value, sensors=current_sensors):
                        current_bad_element = BadElement(
                            enc_name=enc["name"],
                            descriptor=ele_value["descriptor"],
                            status=ele_value["status"],
                            value=ele_value["value"],
                            value_raw=ele_value["value_raw"],
                            enc_title=enc_title,
                        )
                        for previous_bad_element, count in self.bad_elements:
                            if previous_bad_element == current_bad_element:
                                bad_elements.append((current_bad_element, count + 1))
                                break
                        else:
                            bad_elements.append((current_bad_element, 1))

        self.bad_elements = bad_elements

        alerts = []
        for current_bad_element, count in bad_elements:
            # We only report unhealthy enclosure elements if
            # they were unhealthy 5 probes in a row (1 probe = 1 minute)
            if count >= 5:
                try:
                    good_enclosures.remove([current_bad_element.enc_title])
                except ValueError:
                    pass

                alerts.append(
                    Alert(EnclosureUnhealthyAlertClass, args=current_bad_element.args())
                )

        for enclosure in good_enclosures:
            alerts.append(Alert(EnclosureHealthyAlertClass, args=enclosure))

        return alerts
