import cPickle as pickle
import logging
import os

from freenasUI.system.alert import alertPlugins, Alert, BaseAlert
from lockfile import LockFile, LockTimeout

log = logging.getLogger('system.alertmods.smart')

SMART_FILE = '/tmp/.smartalert'


class SMARTAlert(BaseAlert):

    interval = 5

    def run(self):
        alerts = []

        if not os.path.exists(SMART_FILE):
            return alerts

        lock = LockFile(SMART_FILE)

        while not lock.i_am_locking():
            try:
                lock.acquire(timeout=5)
            except LockTimeout:
                return alerts

        with open(SMART_FILE, 'rb') as f:
            try:
                data = pickle.loads(f.read())
            except:
                data = {}

        for msgs in data.itervalues():
            if not msgs:
                continue
            for msg in msgs:
                if msg is None:
                    continue
                alerts.append(Alert(Alert.CRIT, msg))

        lock.release()

        return alerts

alertPlugins.register(SMARTAlert)
