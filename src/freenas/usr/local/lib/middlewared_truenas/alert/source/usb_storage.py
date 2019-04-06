from subprocess import Popen, PIPE

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, ThreadedAlertSource


class USBStorageAlertClass(AlertClass):
    category = AlertCategory.HARDWARE
    level = AlertLevel.CRITICAL
    title = "A USB Storage Has Been Connected to This System"
    text = ("A USB storage device named %s has been connected to this system. Please remove that USB device to "
            "prevent problems with system boot or HA failover.")


class USBStorageAlertSource(ThreadedAlertSource):
    hardware = True

    def check_sync(self):
        proc = Popen('camcontrol devlist -v | grep -m1 -A1 umass', stdout=PIPE, stderr=PIPE, shell=True)
        usbdevname = proc.communicate()
        if proc.returncode == 0:
            usbdevname = str(usbdevname[0])
            usbdevname = usbdevname[usbdevname.find('<')+1:usbdevname.find('>')]

            return Alert(
                USBStorageAlertClass,
                usbdevname,
            )
