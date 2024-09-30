# Copyright (c) - iXsystems Inc.
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions
from dataclasses import dataclass

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

    def args(self):
        return [self.enc_name, self.descriptor, self.status, self.value, self.value_raw]


class EnclosureUnhealthyAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.CRITICAL
    title = "Enclosure Status Is Not Healthy"
    text = 'Enclosure (%s): Element "%s" is reporting a status of "%s" with a value of "%s". (raw value "%s")'
    products = ("SCALE_ENTERPRISE",)


class EnclosureHealthyAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.INFO
    title = "Enclosure Status Is Healthy"
    text = "Enclosure (%s) is healthy."
    products = ("SCALE_ENTERPRISE",)


class EnclosureStatusAlertSource(AlertSource):
    products = ("SCALE_ENTERPRISE",)
    failover_related = True
    run_on_backup_node = False
    bad = ("critical", "noncritical", "unknown", "unrecoverable")
    bad_elements: list | list[tuple[BadElement, int]] = list()

    async def should_report(self, ele_type: str, ele_value: dict[str]):
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

        return True

    async def check(self):
        good_enclosures, bad_elements = [], []
        for enc in await self.middleware.call("enclosure2.query"):
            good_enclosures.append([f"{enc['name']} (id: {enc['id']})"])
            enc["elements"].pop("Array Device Slot")  # dont care about disk slots
            for element_type, element_values in enc["elements"].items():
                for ele_value in element_values.values():
                    if await self.should_report(element_type, ele_value):
                        current_bad_element = BadElement(
                            enc_name=enc["name"],
                            descriptor=ele_value["descriptor"],
                            status=ele_value["status"],
                            value=ele_value["value"],
                            value_raw=ele_value["value_raw"],
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
                    good_enclosures.remove(current_bad_element.enc_name)
                except ValueError:
                    pass

                alerts.append(
                    Alert(EnclosureUnhealthyAlertClass, args=current_bad_element.args())
                )

        for enclosure in good_enclosures:
            alerts.append(Alert(EnclosureHealthyAlertClass, args=enclosure))

        return alerts
