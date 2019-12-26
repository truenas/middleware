import platform

from middlewared.service import Service

from .netif import netif


class InterfaceService(Service):

    class Config:
        namespace_alias = 'interfaces'

    def vlan_setup(self, vlan, disable_capabilities, parent_interfaces):
        self.logger.info('Setting up {}'.format(vlan['vlan_vint']))
        try:
            iface = netif.get_interface(vlan['vlan_vint'])
        except KeyError:
            if platform.system() == 'FreeBSD':
                netif.create_interface(vlan['vlan_vint'])
            if platform.system() == 'Linux':
                netif.create_vlan(vlan['vlan_vint'], vlan['vlan_pint'], vlan['vlan_tag'])
            iface = netif.get_interface(vlan['vlan_vint'])

        if disable_capabilities:
            self.middleware.call('interface.disable_capabilities', vlan['vlan_vint'])

        if iface.parent != vlan['vlan_pint'] or iface.tag != vlan['vlan_tag'] or iface.pcp != vlan['vlan_pcp']:
            iface.unconfigure()
            try:
                iface.configure(vlan['vlan_pint'], vlan['vlan_tag'], vlan['vlan_pcp'])
            except FileNotFoundError:
                self.logger.warn(
                    'VLAN %s parent interface %s not found, skipping.',
                    vlan['vlan_vint'],
                    vlan['vlan_pint'],
                )
                return

        try:
            parent_iface = netif.get_interface(iface.parent)
        except KeyError:
            self.logger.warn('Could not find {} from {}'.format(iface.parent, vlan['vlan_vint']))
            return
        parent_interfaces.append(iface.parent)
        parent_iface.up()
