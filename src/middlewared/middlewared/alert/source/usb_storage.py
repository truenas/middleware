# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from pathlib import Path

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
        for usb in filter(lambda x: x.stem.startswith('usb-'), Path('/dev/disk/by-id').iterdir()):
            if '-part' not in usb.as_posix():
                alerts.append(Alert(USBStorageAlertClass, usb.resolve().as_posix()))
        return alerts
