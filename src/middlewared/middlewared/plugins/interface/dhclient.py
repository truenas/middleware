import os
from contextlib import suppress
from subprocess import PIPE, STDOUT

from middlewared.service import private, Service
from middlewared.utils import Popen
from middlewared.utils.cgroups import move_to_root_cgroups


LEASEFILE_TEMPLATE = '/var/lib/dhcp/dhclient.leases.{}'
PIDFILE_TEMPLATE = '/var/run/dhclient.{}.pid'


class InterfaceService(Service):
    class Config:
        namespace_alias = 'interfaces'

    @private
    async def dhclient_start(self, interface, wait=False):
        cmd = ['dhclient']
        if not wait:
            cmd.append('-nw')
        cmd.extend(['-lf', LEASEFILE_TEMPLATE.format(interface)])
        cmd.extend(['-pf', PIDFILE_TEMPLATE.format(interface)])
        cmd.extend([interface])

        proc = await Popen(cmd, stdout=PIPE, stderr=STDOUT, close_fds=True)
        output = (await proc.communicate())[0].decode()
        if proc.returncode != 0:
            self.logger.error('Failed to run dhclient on %r: %r', interface, output)
        else:
            try:
                with open(PIDFILE_TEMPLATE.format(interface)) as f:
                    pid = int(f.read().strip())
                move_to_root_cgroups(pid)
            except Exception:
                self.logger.warning('Failed to move dhclient to root cgroups', exc_info=True)

    @private
    def dhclient_status(self, interface):
        """
        Get the current status of dhclient for a given `interface`.

        Args:
            interface (str): name of the interface

        Returns:
            tuple(bool, pid): if dhclient is running follow its pid.
        """
        pid = None
        running = False
        with suppress((FileNotFoundError, ValueError, OSError)):
            with open(PIDFILE_TEMPLATE.format(interface)) as f:
                pid = int(f.read().strip())
                os.kill(pid, 0)
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
        with suppress(FileNotFoundError):
            with open(LEASEFILE_TEMPLATE.format(interface)) as f:
                return f.read()
