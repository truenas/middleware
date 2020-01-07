# Copyright (c) 2019 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.
from subprocess import Popen, PIPE

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, ThreadedAlertSource


class USBStorageAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.CRITICAL
    title = "A USB Storage Device Has Been Connected to This System"
    text = ("A USB storage device named %s has been connected to this system. Please remove that USB device to "
            "prevent problems with system boot or HA failover.")

    products = ("ENTERPRISE",)
    hardware = True


class USBStorageAlertSource(ThreadedAlertSource):
    products = ("ENTERPRISE",)

    def check_sync(self):
        proc = Popen('camcontrol devlist -v | grep -m1 -A1 umass', stdout=PIPE, stderr=PIPE, shell=True)
        usbdevname = proc.communicate()
        if proc.returncode == 0:
            usbdevname = str(usbdevname[0])
            usbdevname = usbdevname[usbdevname.find('<') + 1:usbdevname.find('>')]

            return Alert(
                USBStorageAlertClass,
                usbdevname,
            )
