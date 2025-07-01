import asyncio
import contextlib
import ipaddress
from collections import defaultdict
from itertools import zip_longest
from ipaddress import ip_address, ip_interface

from middlewared.api import api_method
from middlewared.api.current import (
    InterfaceEntry, InterfaceBridgeMembersChoicesArgs, InterfaceBridgeMembersChoicesResult,
    InterfaceCancelRollbackArgs, InterfaceCancelRollbackResult, InterfaceCheckinArgs, InterfaceCheckinResult,
    InterfaceCheckinWaitingArgs, InterfaceCheckinWaitingResult, InterfaceChoicesArgs, InterfaceChoicesResult,
    InterfaceCommitArgs, InterfaceCommitResult, InterfaceCreateArgs, InterfaceCreateResult,
    InterfaceDefaultRouteWillBeRemovedArgs, InterfaceDefaultRouteWillBeRemovedResult, InterfaceDeleteArgs,
    InterfaceDeleteResult, InterfaceHasPendingChangesArgs, InterfaceHasPendingChangesResult,
    InterfaceIpInUseArgs, InterfaceIpInUseResult, InterfaceLacpduRateChoicesArgs, InterfaceLacpduRateChoicesResult,
    InterfaceLagPortsChoicesArgs, InterfaceLagPortsChoicesResult, InterfaceRollbackArgs, InterfaceRollbackResult,
    InterfaceSaveDefaultRouteArgs, InterfaceSaveDefaultRouteResult, InterfaceUpdateArgs, InterfaceUpdateResult,
    InterfaceVlanParentInterfaceChoicesArgs, InterfaceVlanParentInterfaceChoicesResult,
    InterfaceWebsocketInterfaceArgs, InterfaceWebsocketInterfaceResult, InterfaceWebsocketLocalIpArgs,
    InterfaceWebsocketLocalIpResult, InterfaceXmitHashPolicyChoicesArgs, InterfaceXmitHashPolicyChoicesResult
)
from middlewared.schema import ValidationErrors
from middlewared.service import CallError, CRUDService, filterable_api_method, pass_app, private
import middlewared.sqlalchemy as sa
from middlewared.utils import filter_list
from .interface.netif import netif
from .interface.interface_types import InterfaceType
from .interface.lag_options import XmitHashChoices, LacpduRateChoices


class NetworkAliasModel(sa.Model):
    __tablename__ = 'network_alias'

    id = sa.Column(sa.Integer(), primary_key=True)
    alias_interface_id = sa.Column(sa.Integer(), sa.ForeignKey('network_interfaces.id', ondelete='CASCADE'), index=True)
    alias_address = sa.Column(sa.String(45), default='')
    alias_version = sa.Column(sa.Integer())
    alias_netmask = sa.Column(sa.Integer())
    alias_address_b = sa.Column(sa.String(45), default='')
    alias_vip = sa.Column(sa.String(45), default='')


class NetworkBridgeModel(sa.Model):
    __tablename__ = 'network_bridge'

    id = sa.Column(sa.Integer(), primary_key=True)
    members = sa.Column(sa.JSON(list), default=[])
    interface_id = sa.Column(sa.ForeignKey('network_interfaces.id', ondelete='CASCADE'))
    stp = sa.Column(sa.Boolean())
    enable_learning = sa.Column(sa.Boolean(), default=True)


class NetworkInterfaceModel(sa.Model):
    __tablename__ = 'network_interfaces'

    id = sa.Column(sa.Integer, primary_key=True)
    int_interface = sa.Column(sa.String(300), unique=True)
    int_name = sa.Column(sa.String(120))
    int_dhcp = sa.Column(sa.Boolean(), default=False)
    int_address = sa.Column(sa.String(45), default='')
    int_address_b = sa.Column(sa.String(45), default='')
    int_version = sa.Column(sa.Integer())
    int_netmask = sa.Column(sa.Integer())
    int_ipv6auto = sa.Column(sa.Boolean(), default=False)
    int_vip = sa.Column(sa.String(45), nullable=True)
    int_vhid = sa.Column(sa.Integer(), nullable=True)
    int_critical = sa.Column(sa.Boolean(), default=False)
    int_group = sa.Column(sa.Integer(), nullable=True)
    int_mtu = sa.Column(sa.Integer(), nullable=True)


class NetworkInterfaceLinkAddressModel(sa.Model):
    __tablename__ = 'network_interface_link_address'

    id = sa.Column(sa.Integer, primary_key=True)
    interface = sa.Column(sa.String(300))
    link_address = sa.Column(sa.String(17), nullable=True)
    link_address_b = sa.Column(sa.String(17), nullable=True)


class NetworkLaggInterfaceModel(sa.Model):
    __tablename__ = 'network_lagginterface'

    id = sa.Column(sa.Integer, primary_key=True)
    lagg_interface_id = sa.Column(sa.Integer(), sa.ForeignKey('network_interfaces.id', ondelete='CASCADE'))
    lagg_protocol = sa.Column(sa.String(120))
    lagg_xmit_hash_policy = sa.Column(sa.String(8), nullable=True)
    lagg_lacpdu_rate = sa.Column(sa.String(4), nullable=True)


class NetworkLaggInterfaceMemberModel(sa.Model):
    __tablename__ = 'network_lagginterfacemembers'

    id = sa.Column(sa.Integer, primary_key=True)
    lagg_ordernum = sa.Column(sa.Integer())
    lagg_physnic = sa.Column(sa.String(120), unique=True)
    lagg_interfacegroup_id = sa.Column(sa.ForeignKey('network_lagginterface.id', ondelete='CASCADE'), index=True)


class NetworkVlanModel(sa.Model):
    __tablename__ = 'network_vlan'

    id = sa.Column(sa.Integer(), primary_key=True)
    vlan_vint = sa.Column(sa.String(120))
    vlan_pint = sa.Column(sa.String(300))
    vlan_tag = sa.Column(sa.Integer())
    vlan_description = sa.Column(sa.String(120))
    vlan_pcp = sa.Column(sa.Integer(), nullable=True)


class InterfaceService(CRUDService):

    class Config:
        datastore_primary_key_type = 'string'
        namespace_alias = 'interfaces'
        cli_namespace = 'network.interface'
        role_prefix = 'NETWORK_INTERFACE'
        entry = InterfaceEntry

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_datastores = {}
        self._rollback_timer = None

    @private
    async def query_names_only(self):
        return [i['int_interface'] for i in await self.middleware.call('datastore.query', 'network.interfaces')]

    @private
    def ignore_usb_nics(self, ha_hardware=None):
        """Currently, there is 0 reason to expose USB based NICs
        using our API on most of the platforms we sell."""
        if ha_hardware is None:
            ha_hardware = self.middleware.call_sync('system.is_ha_capable')

        if ha_hardware:
            # if it's HA capable, 0 reason to show a USB NIC
            # since it's guaranteed to be coming from IPMI or
            # 100% _not_ qualified by our platform team
            return True

        platform = self.middleware.call_sync('truenas.get_chassis_hardware')
        if platform == 'TRUENAS-UNKNOWN' or 'MINI' in platform:
            return False

        return True

    @filterable_api_method(item=InterfaceEntry)
    def query(self, filters, options):
        """
        Query Interfaces with `query-filters` and `query-options`

        `options.extra.retrieve_names_only` (bool): Only return interface names.

        """
        retrieve_names_only = options['extra'].get('retrieve_names_only')
        data = {}
        configs = {
            i['int_interface']: i
            for i in self.middleware.call_sync('datastore.query', 'network.interfaces')
        }
        ha_hardware = self.middleware.call_sync('system.is_ha_capable')
        ignore = self.middleware.call_sync('interface.internal_interfaces')
        ignore_usb_nics = self.ignore_usb_nics(ha_hardware)
        for name, iface in netif.list_interfaces().items():
            if (name in ignore) or (iface.cloned and name not in configs):
                continue
            elif ignore_usb_nics and iface.bus == 'usb':
                continue

            if retrieve_names_only:
                data[name] = {'name': name}
                continue

            try:
                data[name] = self.iface_extend(iface.asdict(), configs, ha_hardware)
            except OSError:
                self.logger.warning('Failed to get interface state for %s', name, exc_info=True)

        for name, config in filter(lambda x: x[0] not in data, configs.items()):
            if retrieve_names_only:
                data[name] = {'name': name}
            else:
                data[name] = self.iface_extend({
                    'name': config['int_interface'],
                    'orig_name': config['int_interface'],
                    'description': config['int_name'],
                    'aliases': [],
                    'link_address': '',
                    'permanent_link_address': None,
                    'hardware_link_address': '',
                    'cloned': True,
                    'mtu': 1500,
                    'flags': [],
                    'nd6_flags': [],
                    'capabilities': [],
                    'link_state': '',
                    'media_type': '',
                    'media_subtype': '',
                    'active_media_type': '',
                    'active_media_subtype': '',
                    'supported_media': [],
                    'media_options': [],
                    'vrrp_config': [],
                }, configs, ha_hardware, fake=True)
        return filter_list(list(data.values()), filters, options)

    @private
    def iface_extend(self, iface_state, configs, ha_hardware, fake=False):
        itype = self.middleware.call_sync('interface.type', iface_state)
        iface = {
            'id': iface_state['name'],
            'name': iface_state['name'],
            'fake': fake,
            'type': itype.value,
            'state': iface_state,
            'aliases': [],
            'ipv4_dhcp': not configs,
            'ipv6_auto': not configs,
            'description': '',
            'mtu': None,
        }
        if ha_hardware:
            iface.update({
                'failover_critical': False,
                'failover_vhid': None,
                'failover_group': None,
                'failover_aliases': [],
                'failover_virtual_aliases': [],
            })
            iface['state']['vrrp_config'] = []

        config = configs.get(iface['name'])
        if not config:
            return iface

        iface.update({
            'ipv4_dhcp': config['int_dhcp'],
            'ipv6_auto': config['int_ipv6auto'],
            'description': config['int_name'],
            'mtu': config['int_mtu'],
        })

        if ha_hardware:
            info = ('INET', 32) if config['int_version'] == 4 else ('INET6', 128)
            iface.update({
                'failover_critical': config['int_critical'],
                'failover_vhid': config['int_vhid'],
                'failover_group': config['int_group'],
            })
            if config['int_address_b']:
                iface['failover_aliases'].append({
                    'type': info[0],
                    'address': config['int_address_b'],
                    'netmask': config['int_netmask'],
                })
            if config['int_vip']:
                iface['failover_virtual_aliases'].append({
                    'type': info[0],
                    'address': config['int_vip'],
                    'netmask': info[1]
                })
                for i in filter(lambda x: x['type'] != 'LINK', iface['state']['aliases']):
                    if i['address'] == config['int_vip']:
                        iface['state']['vrrp_config'].append({'address': config['int_vip'], 'state': 'MASTER'})
                        break
                else:
                    iface['state']['vrrp_config'].append({'state': 'BACKUP'})

        if itype == InterfaceType.BRIDGE:
            filters = [('interface', '=', config['id'])]
            if br := self.middleware.call_sync('datastore.query', 'network.bridge', filters):
                iface.update({
                    'bridge_members': br[0]['members'], 'stp': br[0]['stp'], 'enable_learning': br[0]['enable_learning']
                })
            else:
                iface.update({'bridge_members': [], 'stp': True, 'enable_learning': True})

        elif itype == InterfaceType.LINK_AGGREGATION:
            lag = self.middleware.call_sync(
                'datastore.query',
                'network.lagginterface',
                [('interface', '=', config['id'])],
                {'prefix': 'lagg_'}
            )
            if lag:
                lag = lag[0]
                if lag['protocol'] in ('lacp', 'loadbalance'):
                    iface.update({'xmit_hash_policy': (lag.get('xmit_hash_policy') or 'layer2+3').upper()})
                    if lag['protocol'] == 'lacp':
                        iface.update({'lacpdu_rate': (lag.get('lacpdu_rate') or 'slow').upper()})

                iface.update({'lag_protocol': lag['protocol'].upper(), 'lag_ports': []})
                for port in self.middleware.call_sync(
                    'datastore.query',
                    'network.lagginterfacemembers',
                    [('interfacegroup', '=', lag['id'])],
                    {'prefix': 'lagg_'}
                ):
                    iface['lag_ports'].append(port['physnic'])
            else:
                iface['lag_ports'] = []
        elif itype == InterfaceType.VLAN:
            vlan = self.middleware.call_sync(
                'datastore.query',
                'network.vlan',
                [('vint', '=', iface['name'])],
                {'prefix': 'vlan_'}
            )
            if vlan:
                vlan = vlan[0]
                iface.update({
                    'vlan_parent_interface': vlan['pint'],
                    'vlan_tag': vlan['tag'],
                    'vlan_pcp': vlan['pcp'],
                })
            else:
                iface.update({
                    'vlan_parent_interface': None,
                    'vlan_tag': None,
                    'vlan_pcp': None,
                })

        if (not config['int_dhcp'] or not config['int_ipv6auto']) and config['int_address']:
            iface['aliases'].append({
                'type': 'INET' if config['int_version'] == 4 else 'INET6',
                'address': config['int_address'],
                'netmask': config['int_netmask'],
            })

        filters = [('alias_interface', '=', config['id'])]
        for alias in self.middleware.call_sync('datastore.query', 'network.alias', filters):
            _type = 'INET' if alias['alias_version'] == 4 else 'INET6'
            if alias['alias_address']:
                iface['aliases'].append({
                    'type': _type,
                    'address': alias['alias_address'],
                    'netmask': alias['alias_netmask'],
                })
            if ha_hardware:
                if alias['alias_address_b']:
                    iface['failover_aliases'].append({
                        'type': _type,
                        'address': alias['alias_address_b'],
                        'netmask': alias['alias_netmask'],
                    })
                if alias['alias_vip']:
                    iface['failover_virtual_aliases'].append({
                        'type': _type,
                        'address': alias['alias_vip'],
                        'netmask': 32 if _type == 'INET' else 128,
                    })
                for i in filter(lambda x: x['type'] != 'LINK', iface['state']['aliases']):
                    if i['address'] == alias['alias_vip']:
                        iface['state']['vrrp_config'].append({'address': alias['alias_vip'], 'state': 'MASTER'})
                        break
                else:
                    iface['state']['vrrp_config'].append({'state': 'BACKUP'})

        return iface

    @api_method(
        InterfaceDefaultRouteWillBeRemovedArgs,
        InterfaceDefaultRouteWillBeRemovedResult,
        roles=['NETWORK_INTERFACE_READ']
    )
    def default_route_will_be_removed(self):
        """
        On a fresh install of SCALE, dhclient is started for every interface so IP
        addresses/routes could be installed via that program. However, when the
        end-user goes to configure the first interface we tear down all other interfaces
        configs AND delete the default route. We also remove the default route if the
        configured gateway doesn't match the one currently installed in kernel.
        """
        # FIXME: What about IPv6??
        rtgw = netif.RoutingTable().default_route_ipv4
        if rtgw is None:
            return False

        if not self.middleware.call_sync('datastore.query', 'network.interfaces'):
            return True

        # we have a default route in kernel and we have a route specified in the db
        # and they do not match
        dbgw = self.middleware.call_sync('network.configuration.config')['ipv4gateway']
        return dbgw != rtgw.gateway.exploded

    @api_method(InterfaceSaveDefaultRouteArgs, InterfaceSaveDefaultRouteResult, roles=['NETWORK_INTERFACE_WRITE'])
    async def save_default_route(self, gw):
        """
        This method exists _solely_ to provide a "warning" and therefore
        a path for remediation for when an end-user modifies an interface
        and we rip the default gateway out from underneath them without
        any type of warning.

        NOTE: This makes 2 assumptions
        1. interface.create/update/delete must have been called before
            calling this method
        2. this method must be called before `interface.sync` is called

        This method exists for the predominant scenario for new users...
        1. fresh install SCALE
        2. all interfaces start DHCPv4 (v6 is ignored for now)
        3. 1 of the interfaces receives an IP address
        4. along with the IP, the kernel receives a default route
            (by design, of course)
        5. user goes to configure this interface as having a static
            IP address
        6. as we go through and "sync" the changes, we remove the default
            route because it exists in the kernel FIB but doesn't exist
            in the database.
        7. IF the user is connecting via layer3, then they will lose all
            access to the TrueNAS and never be able to finalize the changes
            to the network because we ripped out the default route which
            is how they were communicating to begin with.

        In the above scenario, we're going to try and prevent this by doing
        the following:
        1. fresh install SCALE
        2. all interfaces start DHCPv4
        3. default route is received
        4. user configures an interface
        5. When user pushes "Test Changes" (interface.sync), webUI will call
            network.configuration.default_route_will_be_removed BEFORE interface.sync
        6. if network.configuration.default_route_will_be_removed returns True,
            then webUI will open a new modal dialog that gives the end-user
            ample warning/verbiage describing the situation. Furthermore, the
            modal will allow the user to input a default gateway
        7. if user gives gateway, webUI will call this method providing the info
            and we'll validate accordingly
        8. OR if user doesn't give gateway, they will need to "confirm" this is
            desired
        9. the default gateway provided to us (if given by end-user) will be stored
            in the same in-memory cache that we use for storing the interface changes
            and will be rolledback accordingly in this plugin just like everything else

        There are a few other scenarios where this is beneficial, but the one listed above
        is seen most often by end-users/support team.
        """
        if not self._original_datastores:
            raise CallError('There are no pending interface changes.')

        gw = ip_address(gw)
        defgw = {'gc_ipv4gateway': gw.exploded}
        for iface in await self.middleware.call('datastore.query', 'network.interfaces'):
            gw_reachable = False
            try:
                gw_reachable = gw in ip_interface(f'{iface["int_address"]}/{iface["int_netmask"]}').network
            except ValueError:
                # these can be "empty" interface entries so there will be no ip or netmask
                # (i.e. when someone creates a VLAN whose parent doesn't have a "config" associated to it)
                continue
            else:
                if gw_reachable:
                    await self.middleware.call('datastore.update', 'network.globalconfiguration', 1, defgw)
                    return

        for iface in await self.middleware.call('datastore.query', 'network.alias'):
            if gw in ip_interface(f'{iface["alias_address"]}/{iface["alias_netmask"]}').network:
                await self.middleware.call('datastore.update', 'network.globalconfiguration', 1, defgw)
                return

        raise CallError(f'{str(gw)!r} is not reachable from any interface on the system.')

    @private
    async def get_datastores(self):
        datastores = {}
        datastores['interfaces'] = await self.middleware.call(
            'datastore.query', 'network.interfaces'
        )
        datastores['alias'] = []
        for i in await self.middleware.call('datastore.query', 'network.alias'):
            i['alias_interface'] = i['alias_interface']['id']
            datastores['alias'].append(i)

        datastores['bridge'] = []
        for i in await self.middleware.call('datastore.query', 'network.bridge'):
            i['interface'] = i['interface']['id'] if i['interface'] else None
            datastores['bridge'].append(i)

        datastores['vlan'] = await self.middleware.call(
            'datastore.query', 'network.vlan'
        )

        datastores['lagg'] = []
        for i in await self.middleware.call('datastore.query', 'network.lagginterface'):
            i['lagg_interface'] = i['lagg_interface']['id']
            datastores['lagg'].append(i)

        datastores['laggmembers'] = []
        for i in await self.middleware.call('datastore.query', 'network.lagginterfacemembers'):
            i['lagg_interfacegroup'] = i['lagg_interfacegroup']['id']
            datastores['laggmembers'].append(i)

        datastores['ipv4gateway'] = {
            'gc_ipv4gateway': (
                await self.middleware.call('datastore.query', 'network.globalconfiguration', [], {'get': True})
            )['gc_ipv4gateway']
        }

        return datastores

    async def __save_datastores(self):
        """
        Save datastores states before performing any actions to interfaces.
        This will make sure to be able to rollback configurations in case something
        doesnt go as planned.
        """
        if self._original_datastores:
            return

        self._original_datastores = await self.get_datastores()

    async def __restore_datastores(self):
        if not self._original_datastores:
            return

        # Deleting network.lagginterface because deleting network.interfaces won't cascade
        # (but network.lagginterface will cascade to network.lagginterfacemembers)
        await self.middleware.call('datastore.delete', 'network.lagginterface', [])
        # Deleting interfaces should cascade to network.alias and network.bridge
        await self.middleware.call('datastore.delete', 'network.interfaces', [])
        await self.middleware.call('datastore.delete', 'network.vlan', [])
        await self.middleware.call('datastore.update', 'network.globalconfiguration', 1, {'gc_ipv4gateway': ''})

        for i in self._original_datastores['interfaces']:
            await self.middleware.call('datastore.insert', 'network.interfaces', i)

        for i in self._original_datastores['alias']:
            await self.middleware.call('datastore.insert', 'network.alias', i)

        for i in self._original_datastores['bridge']:
            await self.middleware.call('datastore.insert', 'network.bridge', i)

        for i in self._original_datastores['vlan']:
            await self.middleware.call('datastore.insert', 'network.vlan', i)

        for i in self._original_datastores['lagg']:
            await self.middleware.call('datastore.insert', 'network.lagginterface', i)

        for i in self._original_datastores['laggmembers']:
            await self.middleware.call('datastore.insert', 'network.lagginterfacemembers', i)

        gw = self._original_datastores['ipv4gateway']
        await self.middleware.call('datastore.update', 'network.globalconfiguration', 1, gw)

        self._original_datastores.clear()

    @private
    async def get_original_datastores(self):
        return self._original_datastores

    @api_method(InterfaceHasPendingChangesArgs, InterfaceHasPendingChangesResult, roles=['NETWORK_INTERFACE_WRITE'])
    async def has_pending_changes(self):
        """
        Return whether there are pending interfaces changes to be applied or not.
        """
        return bool(self._original_datastores)

    @api_method(InterfaceRollbackArgs, InterfaceRollbackResult, roles=['NETWORK_INTERFACE_WRITE'])
    async def rollback(self):
        """
        Rollback pending interfaces changes.
        """
        if self._rollback_timer:
            self._rollback_timer.cancel()
        self._rollback_timer = None
        # We do not check for failover disabled in here because we may be reverting
        # the first time HA is being set up and this was already checked during commit.
        await self.__restore_datastores()

        # All entries are deleted from the network tables on a rollback operation.
        # This breaks `failover.status` on TrueNAS HA systems.
        # Because of this, we need to manually sync the database to the standby
        # controller.
        await self.middleware.call_hook('interface.post_rollback')

        await self.sync()

    @private
    async def checkin_impl(self, clear_cache=True):
        if self._rollback_timer:
            self._rollback_timer.cancel()
        self._rollback_timer = None

        if clear_cache:
            self._original_datastores = {}

    @api_method(InterfaceCheckinArgs, InterfaceCheckinResult, roles=['NETWORK_INTERFACE_WRITE'])
    async def checkin(self):
        """
        If this method is called after interface changes have been committed and within the checkin timeout,
        then the task that automatically rolls back any interface changes is cancelled and the in-memory snapshot
        of database tables for the various interface tables will be cleared. The idea is that the end-user has
        verified the changes work as intended and need to be committed permanently.
        """
        return await self.checkin_impl(clear_cache=True)

    @api_method(InterfaceCancelRollbackArgs, InterfaceCancelRollbackResult, roles=['NETWORK_INTERFACE_WRITE'])
    async def cancel_rollback(self):
        """
        If this method is called after interface changes have been committed and within the checkin timeout,
        then the task that automatically rolls back any interface changes is cancelled and the in-memory snapshot
        of database tables for the various interface tables will NOT be cleared.
        """
        return await self.checkin_impl(clear_cache=False)

    @api_method(InterfaceCheckinWaitingArgs, InterfaceCheckinWaitingResult, roles=['NETWORK_INTERFACE_WRITE'])
    async def checkin_waiting(self):
        """
        Returns whether we are waiting for the user to check in the applied network changes
        before they are rolled back.
        """
        if self._rollback_timer:
            remaining = self._rollback_timer.when() - asyncio.get_event_loop().time()
            if remaining > 0:
                return int(remaining)

    @api_method(InterfaceCommitArgs, InterfaceCommitResult, roles=['NETWORK_INTERFACE_WRITE'])
    async def commit(self, options):
        """
        Commit/apply pending interfaces changes.
        """
        verrors = ValidationErrors()
        schema = 'interface.commit'
        await self.middleware.call('network.common.check_failover_disabled', schema, verrors)
        await self.middleware.call('network.common.check_dhcp_or_aliases', schema, verrors)
        verrors.check()

        try:
            await self.sync()
        except Exception:
            if options['rollback']:
                await self.rollback()
            raise

        if options['rollback'] and options['checkin_timeout']:
            loop = asyncio.get_event_loop()
            self._rollback_timer = loop.call_later(
                options['checkin_timeout'], lambda: self.middleware.create_task(self.rollback())
            )
        else:
            self._original_datastores = {}

    @api_method(InterfaceCreateArgs, InterfaceCreateResult)
    async def do_create(self, data):
        """
        Create virtual interfaces (Link Aggregation, VLAN)

        .. examples(cli)::

        Create a bridge interface:

        > network interface create name=br0 type=BRIDGE bridge_members=enp0s3,enp0s4
            aliases="192.168.0.10"

        Create a link aggregation interface that has multiple IP addresses in multiple subnets:

        > network interface create name=bond0 type=LINK_AGGREGATION lag_protocol=LACP
            lag_ports=enp0s8,enp0s9 aliases="192.168.0.20/30","192.168.1.20/30"

        Create a DHCP-enabled VLAN interface

        > network interface create name=vlan0 type=VLAN vlan_parent_interface=enp0s10
            vlan_tag=10 vlan_pcp=4 ipv4_dhcp=true ipv6_auto=true

        """
        verrors = ValidationErrors()
        await self.middleware.call('network.common.check_failover_disabled', 'interface.create', verrors)

        if data['type'] == 'BRIDGE':
            required_attrs = ('bridge_members', )
        elif data['type'] == 'LINK_AGGREGATION':
            required_attrs = ('lag_protocol', 'lag_ports')
        elif data['type'] == 'VLAN':
            required_attrs = ('vlan_parent_interface', 'vlan_tag')
        for i in filter(lambda x: x not in data, required_attrs):
            verrors.add(f'interface_create.{i}', 'This field is required')
        verrors.check()

        type_ = data['type']
        await self._common_validation(verrors, 'interface_create', data, type_)
        verrors.check()

        await self.__save_datastores()

        name = data.get('name')
        if name is None:
            prefix = {'BRIDGE': 'br', 'LINK_AGGREGATION': 'bond', 'VLAN': 'vlan'}[type_]
            name = await self.get_next(prefix)

        interface_id = lag_id = None
        try:
            async for interface_id in self.__create_interface_datastore(data, {'interface': name}):
                if type_ == 'BRIDGE':
                    await self.middleware.call('datastore.insert', 'network.bridge', {
                        'interface': interface_id, 'members': data['bridge_members'], 'stp': data['stp'],
                        'enable_learning': data['enable_learning']
                    })
                elif type_ == 'LINK_AGGREGATION':
                    lagports_ids = []
                    lag_proto = data['lag_protocol'].lower()
                    xmit = lacpdu_rate = None
                    if lag_proto in ('lacp', 'loadbalance'):
                        # Based on stress testing done by the performance team, we default to layer2+3
                        # because the system default is layer2 and with the system default outbound
                        # traffic did not use the other ports in the lagg. Using layer2+3 fixed it.
                        xmit = data['xmit_hash_policy'].lower() if data['xmit_hash_policy'] is not None else 'layer2+3'

                        if lag_proto == 'lacp':
                            # obviously, lacpdu_rate does not apply to any lagg mode except for lacp
                            lacpdu_rate = data['lacpdu_rate'].lower() if data['lacpdu_rate'] else 'slow'

                    lag_id = await self.middleware.call('datastore.insert', 'network.lagginterface', {
                        'lagg_interface': interface_id,
                        'lagg_protocol': lag_proto,
                        'lagg_xmit_hash_policy': xmit,
                        'lagg_lacpdu_rate': lacpdu_rate,
                    })
                    lagports_ids += await self.__set_lag_ports(lag_id, data['lag_ports'])
                elif type_ == 'VLAN':
                    await self.middleware.call('datastore.insert', 'network.vlan', {
                        'vlan_vint': name,
                        'vlan_pint': data['vlan_parent_interface'],
                        'vlan_tag': data['vlan_tag'],
                        'vlan_pcp': data.get('vlan_pcp'),
                    })
        except Exception:
            if lag_id:
                with contextlib.suppress(Exception):
                    await self.middleware.call('datastore.delete', 'network.lagginterface', lag_id)
            if interface_id:
                await self.middleware.call('datastore.delete', 'network.interfaces', interface_id)
            raise

        return await self.get_instance(name)

    @private
    async def get_next(self, prefix, start=0):
        number = start
        ifaces = [
            i['int_interface']
            for i in await self.middleware.call(
                'datastore.query',
                'network.interfaces',
                [('int_interface', '^', prefix)],
            )
        ]
        while f'{prefix}{number}' in ifaces:
            number += 1
        return f'{prefix}{number}'

    async def _common_validation(self, verrors, schema_name, data, itype, update=None):
        def _get_filters(key):
            return [[key, '!=', update['id']]] if update else []

        cant = ' cannot be changed.'
        required = ' is required when configuring HA.'
        validation_attrs = {
            'aliases': ['Active node IP address', cant, required],
            'failover_aliases': ['Standby node IP address', cant, required],
            'failover_virtual_aliases': ['Virtual IP address', cant, required],
            'failover_group': ['Failover group number', cant, required],
            'mtu': ['MTU', cant],
            'ipv4_dhcp': ['DHCP', cant],
            'ipv6_auto': ['Autoconfig for IPv6', cant],
        }

        ifaces = {i['name']: i for i in await self.middleware.call('interface.query', _get_filters('id'))}
        ds_ifaces = await self.middleware.call('datastore.query', 'network.interfaces', _get_filters('int_interface'))

        if 'name' in data and data['name'] in ifaces:
            verrors.add(f'{schema_name}.name', 'Interface name is already in use.')

        if data.get('ipv4_dhcp') and any(
            filter(lambda x: x['int_dhcp'] and not ifaces[x['int_interface']]['fake'], ds_ifaces)
        ):
            verrors.add(f'{schema_name}.ipv4_dhcp', 'Only one interface can be used for DHCP.')

        if data.get('ipv6_auto') and any(
            filter(lambda x: x['int_ipv6auto'] and not ifaces[x['int_interface']]['fake'], ds_ifaces)
        ):
            verrors.add(
                f'{schema_name}.ipv6_auto',
                'Only one interface can have IPv6 autoconfiguration enabled.'
            )

        await self.middleware.run_in_thread(self.__validate_aliases, verrors, schema_name, data, ifaces)

        bridge_used = {}
        vlan_used = {}
        lag_used = {}
        for k, v in ifaces.items():
            if k.startswith('br'):
                for port in (v.get('bridge_members') or []):
                    bridge_used[port] = k
            elif k.startswith('vlan'):
                vlan_used[k] = v['vlan_parent_interface']
            elif k.startswith('bond'):
                for port in (v.get('lag_ports') or []):
                    lag_used[port] = k

        if itype == 'PHYSICAL':
            if data['name'] in lag_used:
                lag_name = lag_used.get(data['name'])
                for k, v in validation_attrs.items():
                    if data.get(k):
                        verrors.add(
                            f'{schema_name}.{k}',
                            f'Interface in use by {lag_name}. {str(v[0]) + str(v[1])}'
                        )
        elif itype == 'BRIDGE':
            if 'name' in data:
                try:
                    await self.middleware.call('interface.validate_name', InterfaceType.BRIDGE, data['name'])
                except ValueError as e:
                    verrors.add(f'{schema_name}.name', str(e))
            for i, member in enumerate(data.get('bridge_members') or []):
                if member not in ifaces:
                    verrors.add(f'{schema_name}.bridge_members.{i}', 'Not a valid interface.')
                    continue
                if member in bridge_used:
                    verrors.add(
                        f'{schema_name}.bridge_members.{i}',
                        f'Interface {member} is currently in use by {bridge_used[member]}.',
                    )
                elif member in lag_used:
                    verrors.add(
                        f'{schema_name}.bridge_members.{i}',
                        f'Interface {member} is currently in use by {lag_used[member]}.',
                    )
        elif itype == 'LINK_AGGREGATION':
            if 'name' in data:
                try:
                    await self.middleware.call('interface.validate_name', InterfaceType.LINK_AGGREGATION, data['name'])
                except ValueError as e:
                    verrors.add(f'{schema_name}.name', str(e))
            if data['lag_protocol'] not in await self.middleware.call('interface.lag_supported_protocols'):
                verrors.add(
                    f'{schema_name}.lag_protocol',
                    f'TrueNAS SCALE does not support LAG protocol {data["lag_protocol"]}',
                )
            lag_ports = data.get('lag_ports')
            if not lag_ports:
                verrors.add(f'{schema_name}.lag_ports', 'This field cannot be empty.')
            ds_ifaces_set = {i['int_interface'] for i in ds_ifaces}
            for i, member in enumerate(lag_ports):
                _schema = f'{schema_name}.lag_ports.{i}'
                if member not in ifaces:
                    verrors.add(_schema, f'"{member}" is not a valid interface.')
                elif member in lag_used:
                    verrors.add(_schema, f'Interface {member} is currently in use by {lag_used[member]}.')
                elif member in bridge_used:
                    verrors.add(_schema, f'Interface {member} is currently in use by {bridge_used[member]}.')
                elif member in vlan_used:
                    verrors.add(_schema, f'Interface {member} is currently in use by {vlan_used[member]}.')
                elif member in ds_ifaces_set:
                    verrors.add(_schema, f'Interface {member} is currently in use')
        elif itype == 'VLAN':
            if 'name' in data:
                try:
                    await self.middleware.call('interface.validate_name', InterfaceType.VLAN, data['name'])
                except ValueError as e:
                    verrors.add(f'{schema_name}.name', str(e))
            parent = data.get('vlan_parent_interface')
            if parent not in ifaces:
                verrors.add(f'{schema_name}.vlan_parent_interface', 'Not a valid interface.')
            elif parent in lag_used:
                verrors.add(
                    f'{schema_name}.vlan_parent_interface',
                    f'Interface {parent} is currently in use by {lag_used[parent]}.',
                )
            elif parent.startswith('br'):
                verrors.add(
                    f'{schema_name}.vlan_parent_interface',
                    'Bridge interfaces are not allowed.',
                )
            else:
                parent_iface = ifaces[parent]
                mtu = data.get('mtu')
                if mtu and mtu > (parent_iface.get('mtu') or 1500):
                    verrors.add(
                        f'{schema_name}.mtu',
                        'VLAN MTU cannot be bigger than parent interface.',
                    )

        aliases = data.get('aliases', []).copy()
        aliases.extend(data.get('failover_aliases', []).copy())
        aliases.extend(data.get('failover_virtual_aliases', []).copy())
        mtu = data.get('mtu')
        if mtu and mtu < 1280 and any(i['type'] == 'INET6' for i in aliases):
            # we set the minimum MTU to 68 for IPv4 (per https://tools.ietf.org/html/rfc791)
            # however, the minimum MTU for IPv6 is 1280 (per https://tools.ietf.org/html/rfc2460)
            # so we need to make sure that if a IPv6 address is provided the minimum isn't
            # smaller than 1280.
            verrors.add(
                f'{schema_name}.mtu',
                'When specifying an IPv6 address, the MTU cannot be smaller than 1280'
            )

        if not await self.middleware.call('failover.licensed'):
            data.pop('failover_critical', None)
            data.pop('failover_group', None)
            data.pop('failover_aliases', None)
            data.pop('failover_vhid', None)
            data.pop('failover_virtual_aliases', None)
        else:
            failover = await self.middleware.call('failover.config')
            ha_configured = await self.middleware.call('failover.status') != 'SINGLE'
            if ha_configured and not failover['disabled']:
                raise CallError(
                    'Failover needs to be disabled to perform network configuration changes.'
                )

            # have to make sure that active, standby and virtual ip addresses are equal
            active_node_ips = len(data.get('aliases', []))
            standby_node_ips = len(data.get('failover_aliases', []))
            virtual_node_ips = len(data.get('failover_virtual_aliases', []))
            are_equal = active_node_ips == standby_node_ips == virtual_node_ips
            if not are_equal:
                verrors.add(
                    f'{schema_name}.failover_aliases',
                    'The number of active, standby and virtual IP addresses must be the same.'
                )

            if not update:
                failover_attrs = set(
                    [k for k, v in validation_attrs.items() if k not in ('mtu', 'ipv4_dhcp', 'ipv6_auto')]
                )
                configured_attrs = set([i for i in failover_attrs if data.get(i)])

                if configured_attrs:
                    for i in failover_attrs - configured_attrs:
                        verrors.add(
                            f'{schema_name}.{i}',
                            f'{str(validation_attrs[i][0]) + str(validation_attrs[i][2])}',
                        )
            else:
                if data.get('failover_critical') and data.get('failover_group') is None:
                    verrors.add(
                        f'{schema_name}.failover_group',
                        'A failover group is required when configuring a critical failover interface.'
                    )

            # creating a "failover" lagg interface on HA systems and trying
            # to mark it "critical for failover" isn't allowed as it can cause
            # delays in the failover process. (Sometimes failure entirely.)
            # However, using this type of lagg interface for "non-critical"
            # workloads (i.e. webUI management) is acceptable.
            if itype == 'LINK_AGGREGATION':
                # there is a chance that we have failover lagg ints marked critical
                # for failover in the db so to prevent the webUI from disallowing
                # the user to update those interfaces, we'll only enforce this on
                # newly created laggs.
                if not update:
                    if data.get('failover_critical') and data.get('lag_protocol') == 'FAILOVER':
                        msg = 'A bond interface using the "Failover" protocol '
                        msg += 'is not allowed to be marked critical for failover.'
                        verrors.add(f'{schema_name}.failover_critical', msg)
                    elif virtual_node_ips == 0 and data.get('failover_critical'):
                        # We allow "empty" bond configurations because, most often times,
                        # the user will put vlans on top of it. However, some users
                        # will mark the bond interface as critical for failover and
                        # will NOT mark the child interfaces critical for failover. This
                        # paints the false impression that when the bond goes down, a
                        # failover event will be generated. This is not the case because
                        # we act upon network events for generating failover events. If
                        # the bond has no IP address, then it will not generate a failover
                        # event and because the child interface isn't marked critical for
                        # failover, a failover will not take place.
                        msg = 'A bond interface that is marked critical for failover must'
                        msg += ' have ip addresses configured.'
                        verrors.add(f'{schema_name}.failover_critical', msg)

    def __validate_aliases(self, verrors, schema_name, data, ifaces):
        used_networks_ipv4 = []
        used_networks_ipv6 = []
        for iface in ifaces.values():
            for iface_alias in filter(lambda x: x['type'] in ('INET', 'INET6'), iface['aliases']):
                network = ipaddress.ip_network(f'{iface_alias["address"]}/{iface_alias["netmask"]}', strict=False)
                if iface_alias['type'] == 'INET':
                    used_networks_ipv4.append(network)
                else:
                    used_networks_ipv6.append(network)

        for i, alias in enumerate(data.get('aliases') or []):
            alias_network = ipaddress.ip_network(f'{alias["address"]}/{alias["netmask"]}', strict=False)
            if alias_network.version == 4:
                used_networks = ((used_networks_ipv4, 'another interface'),)
            else:
                used_networks = ((used_networks_ipv6, 'another interface'),)

            for network_cidrs, message in used_networks:
                for used_network in network_cidrs:
                    if used_network.overlaps(alias_network):
                        verrors.add(
                            f'{schema_name}.aliases.{i}',
                            f'The network {alias_network} is already in use by {message}.'
                        )
                        break

    async def __convert_interface_datastore(self, data):
        return {
            'name': data['description'],
            'dhcp': data['ipv4_dhcp'],
            'ipv6auto': data['ipv6_auto'],
            'vhid': data.get('failover_vhid'),
            'critical': data.get('failover_critical') or False,
            'group': data.get('failover_group'),
            'mtu': data.get('mtu') or None,
        }

    async def __create_interface_datastore(self, data, attrs):
        interface_attrs, aliases = self.convert_aliases_to_datastore(data)
        interface_attrs.update(attrs)

        interface_id = await self.middleware.call(
            'datastore.insert',
            'network.interfaces',
            dict(**(await self.__convert_interface_datastore(data)), **interface_attrs),
            {'prefix': 'int_'},
        )
        yield interface_id

        for alias in aliases:
            alias['interface'] = interface_id
            await self.middleware.call(
                'datastore.insert', 'network.alias', dict(**alias), {'prefix': 'alias_'}
            )

    @private
    def convert_aliases_to_datastore(self, data):
        da = data['aliases']
        dfa = data.get('failover_aliases', [])
        dfva = data.get('failover_virtual_aliases', [])

        aliases = []
        iface = {'address': '', 'address_b': '', 'netmask': '', 'version': '', 'vip': ''}
        for idx, (a, fa, fva) in enumerate(zip_longest(da, dfa, dfva, fillvalue={})):
            netmask = a['netmask']
            ipa = a['address']
            ipb = fa.get('address', '')
            ipv = fva.get('address', '')
            version = ipaddress.ip_interface(ipa).version
            if idx == 0:
                # first IP address is always written to `network_interface` table
                iface['address'] = ipa
                iface['address_b'] = ipb
                iface['netmask'] = netmask
                iface['version'] = version
                iface['vip'] = ipv
            else:
                # this means it's the 2nd (or more) ip address
                # on a singular interface so we need to write
                # this entry to the alias table
                aliases.append({
                    'address': ipa,
                    'address_b': ipb,
                    'netmask': netmask,
                    'version': version,
                    'vip': ipv,
                })

        return iface, aliases

    async def __set_lag_ports(self, lag_id, lag_ports):
        lagports_ids = []
        for idx, i in enumerate(lag_ports):
            lagports_ids.append(
                await self.middleware.call(
                    'datastore.insert',
                    'network.lagginterfacemembers',
                    {'interfacegroup': lag_id, 'ordernum': idx, 'physnic': i},
                    {'prefix': 'lagg_'},
                )
            )

            # If the link aggregation member was configured we need to reset it,
            # including removing all its IP addresses.
            portinterface = await self.middleware.call(
                'datastore.query',
                'network.interfaces',
                [('interface', '=', i)],
                {'prefix': 'int_'},
            )
            if portinterface:
                portinterface = portinterface[0]
                portinterface.update({
                    'dhcp': False,
                    'address': '',
                    'address_b': '',
                    'netmask': 0,
                    'ipv6auto': False,
                    'vip': '',
                    'vhid': None,
                    'critical': False,
                    'group': None,
                    'mtu': None,
                })
                await self.middleware.call(
                    'datastore.update',
                    'network.interfaces',
                    portinterface['id'],
                    portinterface,
                    {'prefix': 'int_'},
                )
                await self.middleware.call(
                    'datastore.delete',
                    'network.alias',
                    [('alias_interface', '=', portinterface['id'])],
                )
        return lagports_ids

    @api_method(InterfaceUpdateArgs, InterfaceUpdateResult)
    async def do_update(self, oid, data):
        """
        Update Interface of `id`.

        .. examples(cli)::

        Update network interface static IP:

        > network interface update enp0s3 aliases="192.168.0.10"
        """
        verrors = ValidationErrors()
        await self.middleware.call('network.common.check_failover_disabled', 'interface.update', verrors)

        iface = await self.get_instance(oid)

        new = iface.copy()
        new.update(data)

        await self._common_validation(
            verrors, 'interface_update', new, iface['type'], update=iface
        )
        if await self.middleware.call('failover.licensed') and (new.get('ipv4_dhcp') or new.get('ipv6_auto')):
            verrors.add('interface_update.dhcp', 'Enabling DHCPv4/v6 on HA systems is unsupported.')

        verrors.check()

        await self.__save_datastores()

        interface_id = None
        try:

            config = await self.middleware.call(
                'datastore.query', 'network.interfaces', [('int_interface', '=', oid)]
            )
            if not config:
                async for i in self.__create_interface_datastore(new, {
                    'interface': iface['name'],
                }):
                    interface_id = i
                config = (await self.middleware.call(
                    'datastore.query', 'network.interfaces', [('id', '=', interface_id)]
                ))[0]
            else:
                config = config[0]
                if config['int_interface'] != new['name']:
                    await self.middleware.call(
                        'datastore.update',
                        'network.interfaces',
                        config['id'],
                        {'int_interface': new['name']},
                    )

            if iface['type'] == 'PHYSICAL':
                link_address_update = {'link_address': iface['state']['hardware_link_address']}
                if await self.middleware.call('truenas.is_ix_hardware'):
                    if await self.middleware.call('failover.node') == 'B':
                        link_address_update = {'link_address_b': iface['state']['hardware_link_address']}
                link_address_row = await self.middleware.call(
                    'datastore.query', 'network.interface_link_address', [['interface', '=', new['name']]],
                )
                if link_address_row:
                    await self.middleware.call(
                        'datastore.update', 'network.interface_link_address', link_address_row[0]['id'],
                        link_address_update,
                    )
                else:
                    await self.middleware.call(
                        'datastore.insert', 'network.interface_link_address', {
                            'interface': new['name'],
                            'link_address': None,
                            'link_address_b': None,
                            **link_address_update,
                        },
                    )

            if iface['type'] == 'BRIDGE':
                options = {}
                if 'bridge_members' in data:
                    options['members'] = data['bridge_members']
                for key in filter(lambda k: k in data, ('stp', 'enable_learning')):
                    options[key] = data[key]
                if options:
                    filters = [('interface', '=', config['id'])]
                    await self.middleware.call('datastore.update', 'network.bridge', filters, options)
            elif iface['type'] == 'LINK_AGGREGATION':
                xmit = lacpdu = None
                if new['lag_protocol'] in ('LACP', 'LOADBALANCE'):
                    xmit = new.get('xmit_hash_policy', 'layer2+3')
                    if new['lag_protocol'] == 'LACP':
                        lacpdu = new.get('lacpdu_rate', 'slow')

                lag_id = await self.middleware.call(
                    'datastore.update',
                    'network.lagginterface',
                    [('lagg_interface', '=', config['id'])],
                    {
                        'lagg_protocol': new['lag_protocol'].lower(),
                        'lagg_xmit_hash_policy': xmit,
                        'lagg_lacpdu_rate': lacpdu,
                    },
                )
                if 'lag_ports' in data:
                    await self.middleware.call(
                        'datastore.delete',
                        'network.lagginterfacemembers',
                        [('lagg_interfacegroup', '=', lag_id)],
                    )
                    await self.__set_lag_ports(lag_id, data['lag_ports'])
            elif iface['type'] == 'VLAN':
                await self.middleware.call(
                    'datastore.update',
                    'network.vlan',
                    [('vlan_vint', '=', iface['name'])],
                    {
                        'vint': new['name'],
                        'pint': new['vlan_parent_interface'],
                        'tag': new['vlan_tag'],
                        'pcp': new['vlan_pcp'],
                    },
                    {'prefix': 'vlan_'},
                )

            if not interface_id:
                interface_attrs, new_aliases = self.convert_aliases_to_datastore(new)
                await self.middleware.call(
                    'datastore.update', 'network.interfaces', config['id'],
                    dict(**(await self.__convert_interface_datastore(new)), **interface_attrs),
                    {'prefix': 'int_'}
                )

                filters = [('interface', '=', config['id'])]
                prefix = {'prefix': 'alias_'}
                for curr in await self.middleware.call('datastore.query', 'network.alias', filters, prefix):
                    if curr['address'] not in [i['address'] for i in new_aliases]:
                        # being deleted
                        await self.middleware.call('datastore.delete', 'network.alias', curr['id'])
                    else:
                        for idx, new_alias in enumerate(new_aliases[:]):
                            if curr['address'] == new_alias['address']:
                                for i in new_alias.keys():
                                    if curr[i] != new_alias[i]:
                                        # it's being updated
                                        await self.middleware.call(
                                            'datastore.update', 'network.alias', curr['id'], new_alias, prefix
                                        )
                                        new_aliases.pop(idx)
                                        break
                                else:
                                    # nothing has changed but was included in the response
                                    # so ignore it and remove from list
                                    new_aliases.pop(idx)

                # getting here means the remainder of the entries in `new_aliases` are actually
                # new aliases being added
                for new_alias in new_aliases:
                    await self.middleware.call(
                        'datastore.insert',
                        'network.alias',
                        dict(interface=config['id'], **new_alias),
                        {'prefix': 'alias_'}
                    )
        except Exception:
            if interface_id:
                with contextlib.suppress(Exception):
                    await self.middleware.call(
                        'datastore.delete', 'network.interfaces', interface_id
                    )
            raise

        return await self.get_instance(new['name'])

    @api_method(InterfaceDeleteArgs, InterfaceDeleteResult)
    async def do_delete(self, oid):
        """
        Delete Interface of `id`.
        """
        verrors = ValidationErrors()
        schema = 'interface.delete'
        await self.middleware.call('network.common.check_failover_disabled', schema, verrors)

        if iface := await self.get_instance(oid):
            filters = [('type', '=', 'VLAN'), ('vlan_parent_interface', '=', iface['id'])]
            if vlans := ', '.join([i['name'] for i in await self.middleware.call('interface.query', filters)]):
                verrors.add(schema, f'The following VLANs depend on this interface: {vlans}')
            elif iface['type'] == 'BRIDGE' and (
                iface['name'] == (await self.middleware.call('virt.global.config'))['bridge']
            ):
                verrors.add(schema, 'Virt is using this interface as its bridge interface.')

        verrors.check()

        await self.__save_datastores()

        await self.delete_network_interface(oid)

        return oid

    @private
    async def delete_network_interface(self, oid, *, parents=None):
        parents = (parents or set()) | {oid}

        for lagg in await self.middleware.call(
            'datastore.query', 'network.lagginterface', [('lagg_interface__int_interface', '=', oid)]
        ):
            for lagg_member in await self.middleware.call(
                'datastore.query', 'network.lagginterfacemembers', [('lagg_interfacegroup', '=', lagg['id'])]
            ):
                if lagg_member['lagg_physnic'] in parents:
                    continue

                await self.delete_network_interface(lagg_member['lagg_physnic'], parents=parents)

            await self.middleware.call('datastore.delete', 'network.lagginterface', lagg['id'])

        await self.middleware.call(
            'datastore.delete', 'network.vlan', [('vlan_pint', '=', oid)]
        )
        await self.middleware.call(
            'datastore.delete', 'network.vlan', [('vlan_vint', '=', oid)]
        )

        await self.middleware.call(
            'datastore.delete', 'network.interfaces', [('int_interface', '=', oid)]
        )

        return oid

    @api_method(InterfaceWebsocketLocalIpArgs, InterfaceWebsocketLocalIpResult, roles=['NETWORK_INTERFACE_READ'])
    @pass_app()
    async def websocket_local_ip(self, app):
        """Returns the local ip address for this websocket session."""
        try:
            return app.origin.loc_addr
        except AttributeError:
            pass

    @api_method(InterfaceWebsocketInterfaceArgs, InterfaceWebsocketInterfaceResult, roles=['NETWORK_INTERFACE_READ'])
    @pass_app()
    async def websocket_interface(self, app):
        """
        Returns the interface this websocket is connected to.
        """
        local_ip = await self.websocket_local_ip(app)
        if local_ip is None:
            return

        for iface in await self.middleware.call('interface.query'):
            for _ in filter(lambda x: x['address'] == local_ip, iface['aliases'] + iface['state']['aliases']):
                return iface

    @api_method(InterfaceXmitHashPolicyChoicesArgs, InterfaceXmitHashPolicyChoicesResult, authorization_required=False)
    async def xmit_hash_policy_choices(self):
        """
        Available transmit hash policies for the LACP or LOADBALANCE
        lagg type interfaces.
        """
        return {i.value: i.value for i in XmitHashChoices}

    @api_method(InterfaceLacpduRateChoicesArgs, InterfaceLacpduRateChoicesResult, authorization_required=False)
    async def lacpdu_rate_choices(self):
        """
        Available lacpdu rate policies for the LACP lagg type interfaces.
        """
        return {i.value: i.value for i in LacpduRateChoices}

    @api_method(InterfaceChoicesArgs, InterfaceChoicesResult, roles=['NETWORK_INTERFACE_READ'])
    async def choices(self, options):
        """
        Choices of available network interfaces.
        """
        interfaces = await self.middleware.call('interface.query')
        choices = {i['name']: i['description'] or i['name'] for i in interfaces}
        for interface in interfaces:
            if interface['description'] and interface['description'] != interface['name']:
                choices[interface['name']] = f'{interface["name"]}: {interface["description"]}'

            if any(interface['name'].startswith(exclude) for exclude in options['exclude']):
                choices.pop(interface['name'], None)
            if interface['type'] in options['exclude_types']:
                choices.pop(interface['name'], None)
            if not options['lag_ports']:
                if interface['type'] == 'LINK_AGGREGATION':
                    for port in interface['lag_ports']:
                        if port not in options['include']:
                            choices.pop(port, None)
            if not options['bridge_members']:
                if interface['type'] == 'BRIDGE':
                    for member in interface['bridge_members']:
                        if member not in options['include']:
                            choices.pop(member, None)
            if not options['vlan_parent']:
                if interface['type'] == 'VLAN':
                    choices.pop(interface['vlan_parent_interface'], None)
        return choices

    @api_method(
        InterfaceBridgeMembersChoicesArgs,
        InterfaceBridgeMembersChoicesResult,
        roles=['NETWORK_INTERFACE_READ']
    )
    async def bridge_members_choices(self, id_):
        """Return available interface choices that can be added to a `br` (bridge) interface."""
        exclude = {}
        include = {}
        for interface in await self.middleware.call('interface.query'):
            if interface['type'] == 'BRIDGE':
                if id_ and id_ == interface['id']:
                    # means this is an existing br interface that is being updated so we need to
                    # make sure and return the interfaces members
                    include.update({i: i for i in interface['bridge_members']})
                    exclude.update({interface['id']: interface['id']})
                else:
                    # exclude interfaces that are already part of another bridge
                    exclude.update({i: i for i in interface['bridge_members']})
                    # adding a bridge as a member to another bridge is not allowed
                    exclude.update({interface['id']: interface['id']})
            elif interface['type'] == 'LINK_AGGREGATION':
                # exclude interfaces that are already part of a bond interface
                exclude.update({i: i for i in interface['lag_ports']})

            # add the interface to inclusion list and it will be discarded
            # if it was also added to the exclusion list
            include.update({interface['id']: interface['id']})

        return {k: v for k, v in include.items() if k not in exclude}

    @api_method(InterfaceLagPortsChoicesArgs, InterfaceLagPortsChoicesResult, roles=['NETWORK_INTERFACE_READ'])
    async def lag_ports_choices(self, id_):
        """
        Return available interface choices that can be added to a `bond` (lag) interface.
        """
        exclude = {}
        include = {}
        configured_ifaces = await self.middleware.call('interface.query_names_only')
        for interface in await self.middleware.call('interface.query'):
            if interface['type'] == 'LINK_AGGREGATION':
                if id_ and id_ == interface['id']:
                    # means this is an existing bond interface that is being updated so we need to
                    # make sure and return the interfaces members
                    include.update({i: i for i in interface['lag_ports']})
                    exclude.update({interface['id']: interface['id']})
                else:
                    # exclude interfaces that are already part of another bond
                    exclude.update({i: i for i in interface['lag_ports']})
                    # it's perfectly normal to add a bond as a member interface to another bond
                    include.update({interface['id']: interface['id']})
            elif interface['type'] == 'VLAN':
                # adding a vlan or the vlan's parent interface to a bond is not allowed
                exclude.update({interface['id']: interface['id']})
                exclude.update({interface['vlan_parent_interface']: interface['vlan_parent_interface']})
            elif interface['type'] == 'BRIDGE':
                # adding a br interface to a bond is not allowed
                exclude.update({interface['id']: interface['id']})
                # exclude interfaces that are already part of a bridge interface
                exclude.update({i: i for i in interface['bridge_members']})
            elif interface['id'] in configured_ifaces:
                # only remaining type of interface is PHYSICAL but if this is
                # an interface that has already been configured then we obviously
                # don't want to allow it to be added to a bond (user will need
                # to wipe the config of said interface before it can be added)
                exclude.update({interface['id']: interface['id']})

            # add the interface to inclusion list and it will be discarded
            # if it was also added to the exclusion list
            include.update({interface['id']: interface['id']})

        return {k: v for k, v in include.items() if k not in exclude}

    @api_method(
        InterfaceVlanParentInterfaceChoicesArgs,
        InterfaceVlanParentInterfaceChoicesResult,
        roles=['NETWORK_INTERFACE_READ']
    )
    async def vlan_parent_interface_choices(self):
        """
        Return available interface choices for `vlan_parent_interface` attribute.
        """
        return await self.middleware.call('interface.choices', {
            'bridge_members': True,
            'lag_ports': False,
            'vlan_parent': True,
            'exclude_types': [InterfaceType.BRIDGE.value, InterfaceType.VLAN.value],
        })

    @private
    async def sync(self, wait_dhcp=False):
        """
        Sync interfaces configured in database to the OS.
        """
        await self.middleware.call_hook('interface.pre_sync')
        # The VRRP event thread just reads directly from the database
        # so there is no reason to actually configure the interfaces
        # on the OS first. We can update the thread since the db has
        # already been updated by the time this is called.
        await self.middleware.call('vrrpthread.set_non_crit_ifaces')

        interfaces = [i['int_interface'] for i in (await self.middleware.call('datastore.query', 'network.interfaces'))]
        cloned_interfaces = []
        parent_interfaces = []
        sync_interface_opts = defaultdict(dict)

        # First of all we need to create the virtual interfaces
        # LAGG comes first and then VLAN
        laggs = await self.middleware.call('datastore.query', 'network.lagginterface')
        for lagg in laggs:
            name = lagg['lagg_interface']['int_interface']
            members = await self.middleware.call('datastore.query', 'network.lagginterfacemembers',
                                                 [('lagg_interfacegroup_id', '=', lagg['id'])],
                                                 {'order_by': ['lagg_ordernum']})
            cloned_interfaces.append(name)
            try:
                await self.middleware.call(
                    'interface.lag_setup', lagg, members, parent_interfaces, sync_interface_opts
                )
            except Exception:
                self.logger.error('Error setting up LAG %s', name, exc_info=True)

        vlans = await self.middleware.call('datastore.query', 'network.vlan')
        for vlan in vlans:
            cloned_interfaces.append(vlan['vlan_vint'])
            try:
                await self.middleware.call('interface.vlan_setup', vlan, parent_interfaces)
            except Exception:
                self.logger.error('Error setting up VLAN %s', vlan['vlan_vint'], exc_info=True)

        run_dhcp = []
        # Set VLAN interfaces MTU last as they are restricted by underlying interfaces MTU
        for interface in sorted(
            filter(lambda i: not i.startswith('br'), interfaces), key=lambda x: x.startswith('vlan')
        ):
            try:
                if await self.sync_interface(interface, sync_interface_opts[interface]):
                    run_dhcp.append(interface)
            except Exception:
                self.logger.error('Failed to configure {}'.format(interface), exc_info=True)

        bridges = await self.middleware.call('datastore.query', 'network.bridge')
        for bridge in bridges:
            name = bridge['interface']['int_interface']

            cloned_interfaces.append(name)
            try:
                await self.middleware.call('interface.bridge_setup', bridge, parent_interfaces)
            except Exception:
                self.logger.error('Error setting up bridge %s', name, exc_info=True)
            # Finally sync bridge interface
            try:
                if await self.sync_interface(name, sync_interface_opts[name]):
                    run_dhcp.append(name)
            except Exception:
                self.logger.error('Failed to configure {}'.format(name), exc_info=True)

        if run_dhcp:
            # update dhclient.conf before we run dhclient to ensure the hostname/fqdn
            # and/or the supersede routers config options are set properly
            await self.middleware.call('etc.generate', 'dhclient')
            await asyncio.wait([
                self.middleware.create_task(self.run_dhcp(interface, wait_dhcp)) for interface in run_dhcp
            ])

        self.logger.info('Interfaces in database: {}'.format(', '.join(interfaces) or 'NONE'))

        internal_interfaces = tuple(await self.middleware.call('interface.internal_interfaces'))
        dhclient_aws = []
        for name, iface in await self.middleware.run_in_thread(lambda: list(netif.list_interfaces().items())):
            # Skip internal interfaces
            if name.startswith(internal_interfaces):
                continue

            # If there are no interfaces configured we start DHCP on all
            if not interfaces:
                # We should unconfigure interface first before doing autoconfigure. This can be required for cases
                # like the following:
                # 1) Fresh install with system having 1 NIC
                # 2) Configure static ip for the NIC leaving dhcp checked
                # 3) Test changes
                # 4) Do not save changes and wait for time out
                # 5) Rollback happens where the only nic is removed from database
                # 6) If we don't unconfigure, autoconfigure is called which is supposed to start dhclient on the
                #    interface. However this will result in the static ip still being set.
                await self.middleware.call('interface.unconfigure', iface, cloned_interfaces, parent_interfaces)
                if not iface.cloned:
                    # We only autoconfigure physical interfaces because if this is a delete operation
                    # and the interface that was deleted is a "clone" (vlan/br/bond) interface, then
                    # interface.unconfigure deletes the interface. Physical interfaces can't be "deleted"
                    # like virtual interfaces.
                    dhclient_aws.append(asyncio.ensure_future(
                        self.middleware.call('interface.autoconfigure', iface, wait_dhcp)
                    ))
            else:
                # Destroy interfaces which are not in database

                # Skip interfaces in database
                if name in interfaces:
                    continue

                await self.middleware.call('interface.unconfigure', iface, cloned_interfaces, parent_interfaces)

        if wait_dhcp and dhclient_aws:
            await asyncio.wait(dhclient_aws, timeout=30)

        # first interface that is configured, we kill dhclient on _all_ interfaces
        # but dhclient could have added items to /etc/resolv.conf. To "fix" this
        # we run dns.sync which will wipe the contents of resolv.conf and it is
        # expected that the end-user fills this out via the network global webUI page
        # OR if this is a system that has been freshly migrated from CORE to SCALE
        # then we need to make sure that if the user didn't have network configured
        # but left interfaces configured as DHCP only, then we need to generate the
        # /etc/resolv.conf here. In practice, this is a potential race condition
        # here because dhclient could not have received a lease from the dhcp server
        # for all the interfaces that have dhclient running. There is, currently,
        # no better solution unless we redesigned significant portions of our network
        # API to account for this...
        await self.middleware.call('dns.sync')

        try:
            # static routes explicitly defined by the user need to be setup
            await self.middleware.call('staticroute.sync')
        except Exception:
            self.logger.info('Failed to sync static routes', exc_info=True)

        try:
            # We may need to set up routes again as they may have been removed while changing IPs
            await self.middleware.call('route.sync')
        except Exception:
            self.logger.info('Failed to sync routes', exc_info=True)

        await self.middleware.call_hook('interface.post_sync')

    @private
    async def sync_interface(self, name, options=None):
        options = options or {}

        try:
            data = await self.middleware.call(
                'datastore.query', 'network.interfaces',
                [('int_interface', '=', name)], {'get': True}
            )
        except IndexError:
            return

        aliases = await self.middleware.call(
            'datastore.query', 'network.alias',
            [('alias_interface_id', '=', data['id'])]
        )

        return await self.middleware.call('interface.configure', data, aliases, options)

    @private
    async def run_dhcp(self, name, wait_dhcp):
        self.logger.debug('Starting dhclient for {}'.format(name))
        try:
            await self.middleware.call('interface.dhclient_start', name, wait_dhcp)
        except Exception:
            self.logger.error('Failed to run DHCP for {}'.format(name), exc_info=True)

    @api_method(InterfaceIpInUseArgs, InterfaceIpInUseResult, roles=['NETWORK_INTERFACE_READ'])
    def ip_in_use(self, choices):
        """
        Get all IPv4 / Ipv6 from all valid interfaces, excluding tap and epair.
        """
        list_of_ip = []
        static_ips = {}
        # Filter by specified interfaces if provided
        specified_interfaces = choices.get('interfaces', [])
        if choices['static']:
            licensed = self.middleware.call_sync('failover.licensed')
            for i in self.middleware.call_sync('interface.query'):
                if specified_interfaces and i['name'] not in specified_interfaces:
                    continue

                if licensed:
                    for alias in i.get('failover_virtual_aliases') or []:
                        static_ips[alias['address']] = alias['address']
                else:
                    for alias in i['aliases']:
                        static_ips[alias['address']] = alias['address']

        if choices['any']:
            if choices['ipv4']:
                list_of_ip.append({
                    'type': 'INET',
                    'address': '0.0.0.0',
                    'netmask': 0,
                    'broadcast': '255.255.255.255',
                })
            if choices['ipv6']:
                list_of_ip.append({
                    'type': 'INET6',
                    'address': '::',
                    'netmask': 0,
                    'broadcast': 'ff02::1',
                })

        ignore_nics = self.middleware.call_sync('interface.internal_interfaces')
        if choices['loopback']:
            ignore_nics.remove('lo')
            static_ips['127.0.0.1'] = '127.0.0.1'
            static_ips['::1'] = '::1'

        ignore_nics = tuple(ignore_nics)
        for iface in filter(lambda x: not x.orig_name.startswith(ignore_nics), list(netif.list_interfaces().values())):
            # Skip interfaces not in the specified list if interfaces were specified
            if specified_interfaces and iface.orig_name not in specified_interfaces:
                continue
            try:
                aliases_list = iface.asdict()['aliases']
            except FileNotFoundError:
                # This happens on freebsd where we have a race condition when the interface
                # might no longer possibly exist when we try to retrieve data from it
                pass
            else:
                for alias_dict in filter(lambda d: not choices['static'] or d['address'] in static_ips, aliases_list):

                    if choices['ipv4'] and alias_dict['type'] == 'INET':
                        list_of_ip.append(alias_dict)

                    if choices['ipv6'] and alias_dict['type'] == 'INET6':
                        if not choices['ipv6_link_local']:
                            if ipaddress.ip_address(alias_dict['address']) in ipaddress.ip_network('fe80::/64'):
                                continue
                        list_of_ip.append(alias_dict)

        return list_of_ip


async def configure_http_proxy(middleware, *args, **kwargs):
    """
    Configure the `http_proxy` and `https_proxy` environment vars
    from the database.
    """
    gc = await middleware.call('datastore.config', 'network.globalconfiguration')
    http_proxy = gc['gc_httpproxy']
    update = {
        'http_proxy': http_proxy,
        'https_proxy': http_proxy,
    }
    await middleware.call('core.environ_update', update)


async def attach_interface(middleware, iface):
    platform, node_position = await middleware.call('failover.ha_mode')
    if iface == 'ntb0' and platform == 'LAJOLLA2' and node_position == 'B':
        # The f-series platform is an AMD system. This means it's using a different
        # driver for the ntb heartbeat interface (AMD vs Intel). The AMD ntb driver
        # operates subtly differently than the Intel driver. If the A controller
        # is rebooted, the B controllers ntb0 interface is hot-plugged (i.e. removed).
        # When the A controller comes back online, the ntb0 interface is hot-plugged
        # (i.e. added). For this platform we need to re-add the ip address.
        await middleware.call('failover.internal_interface.sync', 'ntb0', '169.254.10.2')
        return

    ignore = await middleware.call('interface.internal_interfaces')
    if any((i.startswith(iface) for i in ignore)):
        return

    if await middleware.call('interface.sync_interface', iface):
        await middleware.call('interface.run_dhcp', iface, False)


async def udevd_ifnet_hook(middleware, data):
    """
    This hook is called on udevd interface type events. It's purpose
    is to:
        1. if this is a physical interface being added
            (all other interface types are ignored)
        2. remove any IPs on said interface if they dont
            exist in the db and/or start dhcp on it
        3. OR add any IPs on said interface if they exist
            in the db
    """
    if data.get('SUBSYSTEM') != 'net' and data.get('ACTION') != 'add':
        return

    iface = data.get('INTERFACE')
    ignore = netif.CLONED_PREFIXES + netif.INTERNAL_INTERFACES
    if iface is None or iface.startswith(ignore):
        # if the udevd event for the interface doesn't have a name (doubt this happens on SCALE)
        # or if the interface startswith CLONED_PREFIXES, then we return since we only care about
        # physical interfaces that are hot-plugged into the system.
        return

    await attach_interface(middleware, iface)


async def __activate_service_announcements(middleware, event_type, args):
    srv = (await middleware.call("network.configuration.config"))["service_announcement"]
    await middleware.call("network.configuration.toggle_announcement", srv)


async def setup(middleware):
    middleware.event_register('network.config', 'Sent on network configuration changes.')

    # Configure http proxy on startup and on network.config events
    middleware.create_task(configure_http_proxy(middleware))
    middleware.event_subscribe('network.config', configure_http_proxy)
    middleware.event_subscribe('system.ready', __activate_service_announcements)
    middleware.register_hook('udev.net', udevd_ifnet_hook)

    # Only run DNS sync in the first run. This avoids calling the routine again
    # on middlewared restart.
    if not await middleware.call('system.ready'):
        try:
            await middleware.call('dns.sync')
        except Exception:
            middleware.logger.error('Failed to setup DNS', exc_info=True)
