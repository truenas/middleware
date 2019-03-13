from middlewared.alert.base import AlertLevel, FilePresenceAlertSource
from middlewared.plugins.disk import GELI_REKEY_FAILED


class VolumeRekeyAlertSource(FilePresenceAlertSource):
    level = AlertLevel.CRITICAL
    title = ("Encrypted volume failed to rekey some disks. Please make "
             "sure you have working recovery keys, check logs files and "
             "correct the error as it may result to data loss.")

    path = GELI_REKEY_FAILED
