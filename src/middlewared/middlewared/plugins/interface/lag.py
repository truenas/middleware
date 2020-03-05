import re
import subprocess

from middlewared.service import Service
from middlewared.utils import osc

from .netif import netif

RE_HWADDR = re.compile(r'hwaddr ([0-9a-f:]+)')
RE_PERMANENT_ADDRESS = re.compile(r'Permanent address: ([0-9a-f:]+)')


class InterfaceService(Service):

    class Config:
        namespace_alias = 'interfaces'

    def lag_setup(self, lagg, members, disable_capabilities, parent_interfaces, sync_interface_opts):
        name = lagg['lagg_interface']['int_interface']
        self.logger.info('Setting up {}'.format(name))
        try:
            iface = netif.get_interface(name)
        except KeyError:
            netif.create_interface(name)
            iface = netif.get_interface(name)

        if disable_capabilities:
            self.middleware.call_sync('interface.disable_capabilities', name)

        protocol = getattr(netif.AggregationProtocol, lagg['lagg_protocol'].upper())
        if iface.protocol != protocol:
            self.logger.info('{}: changing protocol to {}'.format(name, protocol))
            iface.protocol = protocol

        ether = None
        members_database = set()
        members_configured = set(p[0] for p in iface.ports)
        for member in members:
            # For Link Aggregation MTU is configured in parent, not ports
            sync_interface_opts[member['lagg_physnic']]['skip_mtu'] = True
            members_database.add(member['lagg_physnic'])
            try:
                member_iface = netif.get_interface(member['lagg_physnic'])
            except KeyError:
                self.logger.warn('Could not find {} from {}'.format(member['lagg_physnic'], name))
                continue

            if ether is None:
                try:
                    if osc.IS_FREEBSD:
                        cmd = ['ifconfig', member['lagg_physnic']]
                        regex = RE_HWADDR
                    else:
                        cmd = ['ethtool', '-P', member['lagg_physnic']]
                        regex = RE_PERMANENT_ADDRESS

                    result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                            encoding='utf-8', errors='ignore')
                    m = regex.search(result.stdout)
                    if m:
                        ether = m.group(1)

                except Exception:
                    self.logger.warning('Could not get hardware address from %r', member_iface, exc_info=True)

            lagg_mtu = lagg['lagg_interface']['int_mtu'] or 1500
            if member_iface.mtu != lagg_mtu:
                member_name = member['lagg_physnic']
                if member_name in members_configured:
                    iface.delete_port(member_name)
                    members_configured.remove(member_name)
                member_iface.mtu = lagg_mtu

        # Remove member configured but not in database
        for member in (members_configured - members_database):
            iface.delete_port(member)

        # Add member in database but not configured
        for member in (members_database - members_configured):
            iface.add_port(member)

        if ether is not None:
            if osc.IS_FREEBSD:
                cmd = ['ifconfig', name, 'ether', ether]
            else:
                cmd = ['ifconfig', name, 'hw', 'ether', ether]

            result = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    encoding='utf-8', errors='ignore')
            if result.returncode != 0:
                self.logger.warning('Unable to set ethernet address %r for %r: %s', ether, name, result.stderr)

        for port in iface.ports:
            try:
                port_iface = netif.get_interface(port[0])
            except KeyError:
                self.logger.warn('Could not find {} from {}'.format(port[0], name))
                continue
            parent_interfaces.append(port[0])
            port_iface.up()
