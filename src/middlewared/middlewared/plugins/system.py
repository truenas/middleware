from datetime import datetime
from middlewared.schema import accepts, Dict, Int
from middlewared.service import job, Service
from middlewared.utils import Popen

import os
import socket
import struct
import subprocess
import sys
import sysctl
import time

if '/usr/local/lib' not in sys.path:
    sys.path.append('/usr/local/lib')

from freenasOS import Configuration


class SystemService(Service):

    def __init__(self, *args, **kwargs):
        super(SystemService, self).__init__(*args, **kwargs)
        self.__version = None

    @accepts()
    def is_freenas(self):
        """
        Returns `true` if running system is a FreeNAS or `false` is Something Else.
        """
        # This is a stub calling notifier until we have all infrastructure
        # to implement in middlewared
        return self.middleware.call('notifier.is_freenas')

    @accepts()
    def version(self):
        if self.__version is None:
            conf = Configuration.Configuration()
            sys_mani = conf.SystemManifest()
            if sys_mani:
                self.__version = sys_mani.Version()
        return self.__version

    @accepts()
    def info(self):
        """
        Returns basic system information.
        """
        uptime = Popen(
            "env -u TZ uptime | awk -F', load averages:' '{ print $1 }'",
            stdout=subprocess.PIPE,
            shell=True,
        ).communicate()[0].strip()
        return {
            'version': self.version(),
            'hostname': socket.gethostname(),
            'physmem': sysctl.filter('hw.physmem')[0].value,
            'model': sysctl.filter('hw.model')[0].value,
            'loadavg': os.getloadavg(),
            'uptime': uptime,
            'boottime': datetime.fromtimestamp(
                struct.unpack('l', sysctl.filter('kern.boottime')[0].value[:8])[0]
            ),
        }

    @accepts(Dict('system-reboot', Int('delay', required=False), required=False))
    @job()
    def reboot(self, job, options=None):
        """
        Reboots the operating system.
        """
        if options is None:
            options = {}

        self.middleware.send_event('system', 'ADDED', id='reboot', fields={
            'description': 'System is going to reboot',
        })

        delay = options.get('delay')
        if delay:
            time.sleep(delay)

        Popen(["/sbin/reboot"])

    @accepts(Dict('system-shutdown', Int('delay', required=False), required=False))
    @job()
    def shutdown(self, job, options=None):
        """
        Shuts down the operating system.
        """
        if options is None:
            options = {}

        self.middleware.send_event('system', 'ADDED', id='shutdown', fields={
            'description': 'System is going to shutdown',
        })

        delay = options.get('delay')
        if delay:
            time.sleep(delay)

        Popen(["/sbin/poweroff"])
