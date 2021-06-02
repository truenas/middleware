from middlewared.service import private, Service
from middlewared.utils import osc

from .netif import netif


class InterfaceService(Service):

    class Config:
        namespace_alias = 'interfaces'

    @private
    def vlan_setup(self, vlan, disable_capabilities, parent_interfaces):
        self.logger.info('Setting up {}'.format(vlan['vlan_vint']))
        try:
            iface = netif.get_interface(vlan['vlan_vint'])
        except KeyError:
            if osc.IS_FREEBSD:
                netif.create_interface(vlan['vlan_vint'])
            if osc.IS_LINUX:
                try:
                    netif.create_vlan(vlan['vlan_vint'], vlan['vlan_pint'], vlan['vlan_tag'])
                except FileNotFoundError:
                    self.logger.warn(
                        'VLAN %s parent interface %s not found, skipping.',
                        vlan['vlan_vint'],
                        vlan['vlan_pint'],
                    )
                    return
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

        # On HA systems, there seems to be an issue (race in kernel maybe?)
        # that when adding a CARP alias to the interface BEFORE the physical
        # IP address gets added that CARP will stay in INIT state. The only
        # way to get it out of that state is to ifconfig down/up the interface
        # and then it will transition into MASTER/BACKUP accordingly.
        # To workaround this, we up ourselves here explicitly.
        iface.up()
