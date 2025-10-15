import truenas_pynetif as netif

from middlewared.service import private, Service


class InterfaceService(Service):

    class Config:
        namespace_alias = 'interfaces'

    @private
    def vlan_setup(self, vlan, parent_interfaces):
        self.logger.info('Setting up %r', vlan['vlan_vint'])
        try:
            iface = netif.get_interface(vlan['vlan_vint'])
        except KeyError:
            try:
                netif.create_vlan(vlan['vlan_vint'], vlan['vlan_pint'], vlan['vlan_tag'])
            except FileNotFoundError:
                self.logger.warning(
                    'VLAN %r parent interface %r not found, skipping.', vlan['vlan_vint'], vlan['vlan_pint']
                )
                return
            iface = netif.get_interface(vlan['vlan_vint'])

        if iface.parent != vlan['vlan_pint'] or iface.tag != vlan['vlan_tag'] or iface.pcp != vlan['vlan_pcp']:
            iface.unconfigure()
            try:
                iface.configure(vlan['vlan_pint'], vlan['vlan_tag'], vlan['vlan_pcp'])
            except FileNotFoundError:
                self.logger.warning(
                    'VLAN %r parent interface %r not found, skipping.', vlan['vlan_vint'], vlan['vlan_pint']
                )
                return

        try:
            parent_iface = netif.get_interface(iface.parent)
        except KeyError:
            self.logger.warning('Could not find %r from %r', iface.parent, vlan['vlan_vint'])
            return

        parent_interfaces.append(iface.parent)
        parent_iface.up()

        iface.up()
