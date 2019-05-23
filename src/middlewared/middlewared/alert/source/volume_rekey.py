from freenasUI.middleware.notifier import GELI_REKEY_FAILED

from middlewared.alert.base import AlertLevel, FilePresenceAlertSource


class VolumeRekeyAlertSource(FilePresenceAlertSource):
    level = AlertLevel.CRITICAL
    title = "Failed to Rekey Encrypted Pool Disks"
    text = ("Rekeying one or more disks in an encrypted pool failed. Please make "
            "sure working recovery keys are available, check /var/log/messages, and "
            "correct the problem immediately to avoid data loss.")

    path = GELI_REKEY_FAILED

    hardware = True
