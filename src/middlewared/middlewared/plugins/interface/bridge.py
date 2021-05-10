from middlewared.service import private, Service

from .netif import netif


class InterfaceService(Service):

    class Config:
        namespace_alias = 'interfaces'

    @private
    def pre_bridge_setup(self, bridge, sync_interface_opts):
        name = bridge['interface']['int_interface']
        members_database = set(bridge['members'])
        for member in members_database:
            sync_interface_opts[member]['skip_mtu'] = True

        try:
            iface = netif.get_interface(name)
        except KeyError:
            return

        members = set(iface.members)
        for member in members - members_database:
            # These interfaces may be added dynamically for VMs
            if member.startswith(('vnet', 'epair', 'tap')):
                continue
            iface.delete_member(member)

    @private
    def bridge_setup(self, bridge, parent_interfaces):
        name = bridge['interface']['int_interface']
        self.logger.info(f'Setting up {name}')
        try:
            iface = netif.get_interface(name)
        except KeyError:
            netif.create_interface(name)
            iface = netif.get_interface(name)

        mtu = bridge['interface']['int_mtu'] or 1500

        members = set(iface.members)
        members_database = set(bridge['members'])

        for member in members_database:
            try:
                member_iface = netif.get_interface(member)
            except KeyError:
                self.logger.error('Bridge member %s not found', member)
                continue

            if member_iface.mtu != mtu:
                member_iface.mtu = mtu

            if netif.InterfaceFlags.UP not in member_iface.flags:
                member_iface.up()

            parent_interfaces.append(member)

        for member in members_database - members:
            try:
                iface.add_member(member)
            except FileNotFoundError:
                self.logger.error('Bridge member %s not found', member)

        if iface.mtu != mtu:
            iface.mtu = mtu
