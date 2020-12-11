from lockfile import LockFile, LockTimeout
import os
import pickle

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, ThreadedAlertSource

COLLECTD_FILE = "/tmp/.collectdalert"


class CollectdWarningAlertClass(AlertClass):
    category = AlertCategory.REPORTING
    level = AlertLevel.WARNING
    title = "Collectd Warning"

    @classmethod
    def format(cls, args):
        return args


class CollectdCriticalAlertClass(AlertClass):
    category = AlertCategory.REPORTING
    level = AlertLevel.CRITICAL
    title = "Collectd Critical Alert"

    @classmethod
    def format(cls, args):
        return args


class CollectdAlertSource(ThreadedAlertSource):
    def check_sync(self):
        if not os.path.exists(COLLECTD_FILE):
            return

        lock = LockFile(COLLECTD_FILE)

        while not lock.i_am_locking():
            try:
                lock.acquire(timeout=5)
            except LockTimeout:
                return

        with open(COLLECTD_FILE, "rb") as f:
            try:
                data = pickle.loads(f.read())
            except Exception:
                data = {}

        lock.release()

        alerts = []
        for k, v in list(data.items()):
            if k == "ctl-ha/disk_octets":
                text = (
                    "Storage Controller HA link is in use. Please check that all iSCSI and FC initiators support ALUA "
                    "and are able to connect to the active node."
                )
            else:
                text = k

            if v["Severity"] == "WARNING":
                klass = CollectdWarningAlertClass
            else:
                klass = CollectdCriticalAlertClass

            alerts.append(Alert(klass, text))

        return alerts
