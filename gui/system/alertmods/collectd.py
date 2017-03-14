import pickle as pickle
import logging
import os

from freenasUI.system.alert import alertPlugins, Alert, BaseAlert
from lockfile import LockFile, LockTimeout

log = logging.getLogger('system.alertmods.collectd')

COLLECTD_FILE = '/tmp/.collectdalert'


class CollectdAlert(BaseAlert):

    def run(self):
        alerts = []

        if not os.path.exists(COLLECTD_FILE):
            return alerts

        lock = LockFile(COLLECTD_FILE)

        while not lock.i_am_locking():
            try:
                lock.acquire(timeout=5)
            except LockTimeout:
                return alerts

        with open(COLLECTD_FILE, 'rb') as f:
            try:
                data = pickle.loads(f.read())
            except:
                data = {}

        lock.release()

        for k, v in list(data.items()):
            if v['Severity'] == 'WARNING':
                l = Alert.WARN
            else:
                l = Alert.CRIT
            if k == 'ctl-ha/disk_octets':
                msg = "CTL HA link is actively used, check initiators connectivity"
            else:
                msg = k
            alerts.append(Alert(l, msg))

        return alerts

alertPlugins.register(CollectdAlert)
