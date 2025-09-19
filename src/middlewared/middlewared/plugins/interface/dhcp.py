import os
import time
from contextlib import suppress
from subprocess import run, PIPE, STDOUT, DEVNULL

from middlewared.service import private, Service


class InterfaceService(Service):
    class Config:
        namespace_alias = 'interfaces'

    @private
    def _get_dhcpcd_pid_for_interface(self, interface):
        """Get the PID of the dhcpcd daemon for a specific interface."""
        pidfile = f'/run/dhcpcd/{interface}.pid'
        with suppress(FileNotFoundError, ValueError):
            with open(pidfile) as f:
                pid = int(f.read().strip())
                try:
                    os.kill(pid, 0)
                    return pid
                except OSError:
                    pass
        return None

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
        """Start DHCP on the specified interface using systemd."""
        # Start the ix-dhcpcd service for this interface using systemd
        cmd = ['systemctl', 'start', f'ix-dhcpcd@{interface}.service']

        proc = run(cmd, stdout=PIPE, stderr=STDOUT)
        if proc.returncode != 0:
            self.logger.error('Failed to start dhcpcd for interface %r: %r', interface, proc.stdout.decode())
            return

        # If wait is True, wait for the service to be fully active
        if wait:
            # Wait for the service to become active
            cmd = ['systemctl', 'is-active', f'ix-dhcpcd@{interface}.service']
            for _ in range(30):  # Wait up to 30 seconds
                proc = run(cmd, stdout=DEVNULL, stderr=DEVNULL)
                if proc.returncode == 0:
                    break
                time.sleep(1)

    @private
    def dhcp_status(self, interface):
        """
        Get the current status of DHCP for a given `interface`.

        Args:
            interface (str): name of the interface

        Returns:
            tuple(bool, pid): if DHCP is active for the interface and the daemon pid.
        """
        # Check if the systemd service is active
        cmd = ['systemctl', 'is-active', f'ix-dhcpcd@{interface}.service']
        proc = run(cmd, stdout=DEVNULL, stderr=DEVNULL)

        if proc.returncode == 0:
            # Service is active, get the PID
            pid = self._get_dhcpcd_pid_for_interface(interface)
            return True, pid

        return False, None

    @private
    def dhcp_stop(self, interface):
        """Stop DHCP on a specific interface."""
        # Stop the ix-dhcpcd service for this interface using systemd
        run(['systemctl', 'stop', f'ix-dhcpcd@{interface}.service'], capture_output=True)

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
