import os
import platform
import subprocess

from middlewared.service import private, Service
from middlewared.utils import Popen


if platform.system() == 'FreeBSD':
    LEASEFILE_TEMPLATE = '/var/db/dhclient.leases.{}'
    PIDFILE_TEMPLATE = '/var/run/dhclient/dhclient.{}.pid'
else:
    LEASEFILE_TEMPLATE = '/var/lib/dhcp/dhclient.leases.{}'
    PIDFILE_TEMPLATE = '/var/run/dhclient.{}.pid'


class InterfaceService(Service):
    class Config:
        namespace_alias = 'interfaces'

    @private
    async def dhclient_start(self, interface, wait=False):
        cmd = ['dhclient']

        if platform.system() == 'FreeBSD':
            if not wait:
                cmd.append('-b')

        if platform.system() == 'Linux':
            if not wait:
                cmd.append('-nw')

            cmd.extend(['-lf', LEASEFILE_TEMPLATE.format(interface)])
            cmd.extend(['-pf', PIDFILE_TEMPLATE.format(interface)])

        proc = await Popen(
            cmd + [interface],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, close_fds=True,
        )
        output = (await proc.communicate())[0].decode()
        if proc.returncode != 0:
            self.logger.error('Failed to run dhclient on {}: {}'.format(
                interface, output,
            ))

    @private
    def dhclient_status(self, interface):
        """
        Get the current status of dhclient for a given `interface`.

        Args:
            interface (str): name of the interface

        Returns:
            tuple(bool, pid): if dhclient is running follow its pid.
        """
        pidfile = PIDFILE_TEMPLATE.format(interface)
        pid = None
        if os.path.exists(pidfile):
            with open(pidfile, 'r') as f:
                try:
                    pid = int(f.read().strip())
                except ValueError:
                    pass

        running = False
        if pid:
            try:
                os.kill(pid, 0)
            except OSError:
                pass
            else:
                running = True
        return running, pid

    @private
    def dhclient_leases(self, interface):
        """
        Reads the leases file for `interface` and returns the content.

        Args:
            interface (str): name of the interface.

        Returns:
            str: content of dhclient leases file for `interface`.
        """
        leasesfile = LEASEFILE_TEMPLATE.format(interface)
        if os.path.exists(leasesfile):
            with open(leasesfile, 'r') as f:
                return f.read()
