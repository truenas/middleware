import os
from contextlib import suppress
from subprocess import run, PIPE, STDOUT

from middlewared.service import private, Service
from middlewared.utils.cgroups import move_to_root_cgroups


DHCPCD_PIDFILE = '/var/run/dhcpcd/pid'
DHCPCD_LEASE_DIR = '/var/lib/dhcpcd/'


class InterfaceService(Service):
    class Config:
        namespace_alias = 'interfaces'

    @private
    def _is_dhcpcd_running(self):
        """Check if the dhcpcd master daemon is running."""
        with suppress(FileNotFoundError, ValueError):
            with open(DHCPCD_PIDFILE) as f:
                pid = int(f.read().strip())
                try:
                    os.kill(pid, 0)
                    return True, pid
                except OSError:
                    pass
        return False, None

    @private
    def _get_dhcpcd_pid(self):
        """Get the PID of the dhcpcd daemon."""
        running, pid = self._is_dhcpcd_running()
        return pid if running else None

    @private
    def _parse_dhcpcd_output(self, output):
        """Parse dhcpcd -U output which returns shell variable format."""
        lease_info = {}
        for line in output.strip().split('\n'):
            if '=' in line:
                key, value = line.split('=', 1)
                # Remove quotes if present
                value = value.strip('\'"')
                lease_info[key] = value
        return lease_info

    @private
    def dhcp_start(self, interface, wait=False):
        """Start DHCP on the specified interface using dhcpcd."""
        # First check if dhcpcd daemon is running
        running, pid = self._is_dhcpcd_running()

        if not running:
            # Start the dhcpcd master daemon
            cmd = ['dhcpcd', '-b', '-q']
            if not wait:
                cmd.append('-B')  # Background immediately

            proc = run(cmd, stdout=PIPE, stderr=STDOUT)
            if proc.returncode != 0:
                self.logger.error('Failed to start dhcpcd daemon: %r', proc.stdout.decode())
                return

            # Get the new PID and move to root cgroups
            try:
                running, pid = self._is_dhcpcd_running()
                if pid:
                    move_to_root_cgroups(pid)
            except Exception:
                self.logger.warning('Failed to move dhcpcd to root cgroups', exc_info=True)
        else:
            # Daemon is running, just rebind the interface
            # This will make dhcpcd request a lease for this interface
            cmd = ['dhcpcd', '-n', interface]
            proc = run(cmd, stdout=PIPE, stderr=STDOUT)
            if proc.returncode != 0:
                self.logger.error('Failed to start DHCP on %r: %r', interface, proc.stdout.decode())

    @private
    def dhcp_status(self, interface):
        """
        Get the current status of DHCP for a given `interface`.

        Args:
            interface (str): name of the interface

        Returns:
            tuple(bool, pid): if DHCP is active for the interface and the daemon pid.
        """
        # Check if dhcpcd daemon is running
        running, pid = self._is_dhcpcd_running()
        if not running:
            return False, None

        # Check if this interface has an active lease
        # dhcpcd -U returns 0 if interface has a lease
        result = run(['dhcpcd', '-U', interface], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return True, pid

        return False, None

    @private
    def dhcp_stop(self, interface):
        """Stop DHCP on a specific interface."""
        # Release and remove the interface from dhcpcd
        run(['dhcpcd', '-k', interface], capture_output=True)

    @private
    def dhcp_leases(self, interface):
        """
        Get the lease information for `interface`.

        Args:
            interface (str): name of the interface.

        Returns:
            str: lease information in text format (for compatibility).
        """
        # Get lease info using dhcpcd -U
        result = run(['dhcpcd', '-U', interface], capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            # Convert to a format similar to dhclient leases for compatibility
            lease_info = self._parse_dhcpcd_output(result.stdout)

            # Build a dhclient-like lease format for backward compatibility
            lease_text = []
            if 'ip_address' in lease_info:
                # Extract just the IP without the subnet
                ip = lease_info['ip_address'].split('/')[0]
                lease_text.append(f"fixed-address {ip};")

            if 'subnet_mask' in lease_info:
                lease_text.append(f"option subnet-mask {lease_info['subnet_mask']};")
            elif 'ip_address' in lease_info and '/' in lease_info['ip_address']:
                # Calculate subnet mask from CIDR if available
                cidr = int(lease_info['ip_address'].split('/')[1])
                mask_int = (0xffffffff << (32 - cidr)) & 0xffffffff
                mask = '.'.join([str((mask_int >> (8 * (3 - i))) & 0xff) for i in range(4)])
                lease_text.append(f"option subnet-mask {mask};")

            if 'routers' in lease_info:
                lease_text.append(f"option routers {lease_info['routers']};")

            if 'domain_name_servers' in lease_info:
                lease_text.append(f"option domain-name-servers {lease_info['domain_name_servers'].replace(' ', ', ')};")

            return '\n'.join(lease_text) if lease_text else None

        return None

    # Compatibility aliases for old method names during transition
    @private
    def dhclient_start(self, interface, wait=False):
        """Compatibility wrapper for dhcp_start."""
        return self.dhcp_start(interface, wait)

    @private
    def dhclient_status(self, interface):
        """Compatibility wrapper for dhcp_status."""
        return self.dhcp_status(interface)

    @private
    def dhclient_leases(self, interface):
        """Compatibility wrapper for dhcp_leases."""
        return self.dhcp_leases(interface)
