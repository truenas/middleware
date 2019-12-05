from middlewared.service import Service

from .netif import netif


class InterfaceService(Service):

    class Config:
        namespace_alias = 'interfaces'

    def bridge_setup(self, bridge):
        name = bridge['interface']['int_interface']
        self.logger.info(f'Setting up {name}')
        try:
            iface = netif.get_interface(name)
        except KeyError:
            netif.create_interface(name)
            iface = netif.get_interface(name)

        members = set(iface.members)
        members_database = set(bridge['members'])

        for member in members_database - members:
            try:
                iface.add_member(member)
            except FileNotFoundError:
                self.logger.error('Bridge member %s not found', member)

        for member in members - members_database:
            # These interfaces may be added dynamically for Jails/VMs
            if member.startswith(('vnet', 'epair', 'tap')):
                continue
            iface.delete_member(member)
