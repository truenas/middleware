from lockfile import LockFile, LockTimeout
import os
import pickle

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, Alert, ThreadedAlertSource

COLLECTD_FILE = "/tmp/.collectdalert"


class CollectdWarningAlertClass(AlertClass):
    category = AlertCategory.REPORTING
    level = AlertLevel.WARNING
    title = "Collectd warning"

    def format(cls, args):
        return args


class CollectdCriticalAlertClass(AlertClass):
    category = AlertCategory.REPORTING
    level = AlertLevel.CRITICAL
    title = "Collectd critical alert"

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
                title = "CTL HA link is actively used, check initiators connectivity"
            else:
                title = k

            if v["Severity"] == "WARNING":
                klass = CollectdWarningAlertClass
            else:
                klass = CollectdCriticalAlertClass

            alerts.append(Alert(klass, title))

        return alerts
