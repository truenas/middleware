from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, FilePresenceAlertSource
from middlewared.plugins.disk import GELI_REKEY_FAILED


class VolumeRekeyAlertClass(AlertClass):
    category = AlertCategory.STORAGE
    level = AlertLevel.CRITICAL
    title = "Encrypted volume failed to rekey some disks"
    text = ("Encrypted volume failed to rekey some disks. Please make "
            "sure you have working recovery keys, check logs files and "
            "correct the error as it may result to data loss.")


class VolumeRekeyAlertSource(FilePresenceAlertSource):
    path = GELI_REKEY_FAILED
    klass = VolumeRekeyAlertClass
