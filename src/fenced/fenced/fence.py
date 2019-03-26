import hashlib
import logging
import os
import sysctl
import time

logger = logging.getLogger(__name__)
LICENSE_FILE = '/data/license'


class Fence(object):

    def __init__(self, interval, force):
        self._interval = interval
        self._force = force
        self._hostid = None

    def get_hostid(self):
        hostid = sysctl.filter('kern.hostid')[0].value | 1 << 31
        hostid &= 0xffffffff
        # Certain Supermicro systems does not supply hostid. Workaround by using a
        # blacklist and derive the value from the license.
        if hostid == 0xfe4ac89c and os.path.exists(LICENSE_FILE):
            with open(LICENSE_FILE, 'rb') as f:
                license = hashlib.md5(f.read()).hexdigest()[:8]
                if license[0] == '0':
                    license = f'8{license[-7:]}'
                hostid = int(license, 16)
        return hostid

    def run(self):
        self._hostid = self.get_hostid()
        self.loop()

    def loop(self):
        while True:
            time.sleep(self._interval)
