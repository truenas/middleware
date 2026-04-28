# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions
from dataclasses import dataclass
from typing import Any

from middlewared.alert.base import (
    Alert,
    AlertCategory,
    AlertClass,
    AlertClassConfig,
    AlertLevel,
    AlertSource,
    NonDataclassAlertClass,
)
from middlewared.utils import ProductType


@dataclass(slots=True, frozen=True, kw_only=True)
class BadElement:
    enc_name: str
    descriptor: str
    status: str
    value: str
    value_raw: int
    enc_title: str

    def args(self) -> list[str | int]:
        return [self.enc_name, self.descriptor, self.status, self.value, self.value_raw]


class EnclosureUnhealthyAlert(NonDataclassAlertClass[list[str | int]], AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.HARDWARE,
        level=AlertLevel.CRITICAL,
        title="Enclosure Status Is Not Healthy",
        text='Enclosure (%s): Element "%s" is reporting a status of "%s" with a value of "%s". (raw value "%s")',
        products=(ProductType.ENTERPRISE,),
    )


class EnclosureHealthyAlert(NonDataclassAlertClass[list[str]], AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.HARDWARE,
        level=AlertLevel.INFO,
        title="Enclosure Status Is Healthy",
        text="Enclosure (%s) is healthy.",
        products=(ProductType.ENTERPRISE,),
    )


class EnclosureStatusAlertSource(AlertSource):
    products = (ProductType.ENTERPRISE,)
    failover_related = True
    run_on_backup_node = False
    bad = ("critical", "noncritical", "unknown", "unrecoverable")
    bad_elements: list[tuple[BadElement, int]] = list()

    async def should_report(self, ele_type: str, ele_value: dict[str, Any], model: str = "") -> bool:
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
        elif (
            model in ("ES60G1", "ES60G2")
            and ele_type == "Current Sensor"
            and ele_value["descriptor"].startswith("CURR IOM")
            and ele_value["value_raw"] == 0x02400000  # Critical, Fail on, 0.0A
        ):
            # ES60G1/ES60G2 JBOD enclosures (HGST H4060-J) assert "Fail on" on
            # IOM current sensors when drives draw no current on that rail. This
            # is a false positive caused by 12V-primary drives (e.g. Kioxia PM7)
            # that legitimately draw 0A on the 5V rail. The 12V IOM sensors on
            # the same enclosure show healthy current, confirming drives are powered.
            return False

        return True

    async def check(self) -> list[Alert[Any]]:
        good_enclosures: list[list[str]] = []
        bad_elements: list[tuple[BadElement, int]] = []
        for enc in await self.middleware.call("enclosure2.query"):
            enc_title = f"{enc['name']} (id: {enc['id']})"
            good_enclosures.append([enc_title])
            enc["elements"].pop("Array Device Slot", None)  # dont care about disk slots
            for element_type, element_values in enc["elements"].items():
                for ele_value in element_values.values():
                    if await self.should_report(element_type, ele_value, enc["model"]):
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

        alerts: list[Alert[Any]] = []
        for current_bad_element, count in bad_elements:
            # We only report unhealthy enclosure elements if
            # they were unhealthy 5 probes in a row (1 probe = 1 minute)
            if count >= 5:
                try:
                    good_enclosures.remove([current_bad_element.enc_title])
                except ValueError:
                    pass

                alerts.append(
                    Alert(EnclosureUnhealthyAlert(current_bad_element.args()))
                )

        for enclosure in good_enclosures:
            alerts.append(Alert(EnclosureHealthyAlert(enclosure)))

        return alerts
