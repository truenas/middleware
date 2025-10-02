# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

import os

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, ThreadedAlertSource
from middlewared.utils import ProductType


class USBStorageAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.CRITICAL
    title = 'A USB Storage Device Has Been Connected to This System'
    text = ('A USB storage device %r has been connected to this system. Please remove that USB device to '
            'prevent problems with system boot or HA failover.')
    products = (ProductType.ENTERPRISE,)
    proactive_support = True


class USBStorageAlertSource(ThreadedAlertSource):
    products = (ProductType.ENTERPRISE,)

    def check_sync(self):
        alerts = []
        with os.scandir("/dev/disk/by-id") as sdir:
            for i in filter(lambda x: x.name.lower().startswith("usb-"), sdir):
                resolved_path = os.path.realpath(i.path)
                if resolved_path.startswith("/dev/sr"):
                    # When opening the IPMI KVM console on the
                    # {f/v}-series platforms, a USB CDROM device
                    # is automatically added to OS without the
                    # user actually mounting an ISO. In this
                    # scenario, we need to ignore the device.
                    continue
                elif "-part" not in i.name:
                    alerts.append(Alert(USBStorageAlertClass, resolved_path))
        return alerts
