import os
import subprocess

from middlewared.service import private, Service
from middlewared.utils import osc, Popen
from middlewared.utils.cgroups import move_to_root_cgroups


if osc.IS_FREEBSD:
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

        if osc.IS_FREEBSD:
            if not wait:
                cmd.append('-b')

        if osc.IS_LINUX:
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
        else:
            if osc.IS_LINUX:
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
