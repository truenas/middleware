from lockfile import LockFile, LockTimeout
import os
import pickle

from middlewared.alert.base import Alert, AlertLevel, ThreadedAlertSource

COLLECTD_FILE = "/tmp/.collectdalert"


class CollectdAlertSource(ThreadedAlertSource):
    level = AlertLevel.WARNING
    title = "Collectd Warning"

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
                title = (
                    "Storage Controller HA link is in use. Please check that all iSCSI and FC initiators support ALUA and "
                    "are able to connect to the active node."
                )
            else:
                title = k

            if v["Severity"] == "WARNING":
                level = AlertLevel.WARNING
            else:
                level = AlertLevel.CRITICAL

            alerts.append(Alert(title, level=level))

        return alerts
