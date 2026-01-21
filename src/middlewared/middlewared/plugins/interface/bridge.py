from truenas_pynetif.bits import InterfaceFlags
from truenas_pynetif.netif import create_interface, get_interface

from middlewared.service import private, Service


class InterfaceService(Service):

    class Config:
        namespace_alias = 'interfaces'

    @private
    def bridge_setup(self, bridge, parent_interfaces):
        name = bridge['interface']['int_interface']
        bridge_mtu = bridge['interface']['int_mtu'] or 1500
        try:
            iface = get_interface(name)
        except KeyError:
            create_interface(name)
            iface = get_interface(name)

        self.logger.info('Setting up %r', name)

        if iface.mtu != bridge_mtu:
            self.logger.info('Setting %r MTU to %d', name, bridge_mtu)
            iface.mtu = bridge_mtu

        db_members = set(bridge['members'])
        os_members = set(iface.members)
        for member in os_members - db_members:
            # We do not remove vnetX interfaces from bridge as they would be consumed by libvirt
            if member.startswith('vnet'):
                continue

            # remove members from the bridge that aren't in the db
            self.logger.info('Removing member interface %r from %r', member, name)
            iface.delete_member(member)

        for member in db_members - os_members:
            # now add members that are written in db but do not exist in
            # the bridge on OS side
            try:
                self.logger.info('Adding member interface %r to %r', member, name)
                iface.add_member(member)
            except FileNotFoundError:
                self.logger.error('Bridge member %r not found', member)
                continue

            # now make sure the bridge member is up
            member_iface = get_interface(member)
            if InterfaceFlags.UP not in member_iface.flags:
                self.logger.info('Bringing up member interface %r in %r', member_iface.name, name)
                member_iface.up()

        for member in db_members:
            parent_interfaces.append(member)
            iface.set_learning(member, bridge.get('enable_learning', True))

        if iface.stp != bridge['stp']:
            verb = 'off' if not bridge['stp'] else 'on'
            self.logger.info(f'Turning STP {verb} for {name!r}')
            iface.toggle_stp(name, int(bridge['stp']))

        # finally we need to up the main bridge if it's not already up
        if InterfaceFlags.UP not in iface.flags:
            self.logger.info('Bringing up %r', name)
            iface.up()
