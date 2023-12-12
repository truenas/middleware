import middlewared.sqlalchemy as sa
from middlewared.schema import accepts, Dict, Int, IPAddr, Password, Patch, Str
from middlewared.service import CRUDService, private, ValidationErrors
from middlewared.utils.license import LICENSE_ADDHW_MAPPING

from middlewared.plugins.jbof.redfish import RedfishClient, InvalidCredentialsError
from .functions import decode_static_ip, initiator_static_ip, jbof_static_ip, initiator_ip_from_jbof_static_ip, jbof_static_ip_from_initiator_ip, static_ip_netmask_int, static_ip_netmask_str, static_mtu


class JBOFModel(sa.Model):
    __tablename__ = 'storage_jbof'

    id = sa.Column(sa.Integer(), primary_key=True)

    jbof_description = sa.Column(sa.String(120), nullable=True)

    # When performing static (code-based) assignment of data-plane IPs, we
    # want each JBOD to have a deterministic unique index that counts up from
    # zero (without any gaps, which rules out using the id).  This will not be
    # part of the public API.
    jbof_index = sa.Column(sa.Integer(), unique=True)
    jbof_uuid = sa.Column(sa.Text(), nullable=False, unique=True)

    jbof_mgmt_ip1 = sa.Column(sa.String(45), nullable=False)
    jbof_mgmt_ip2 = sa.Column(sa.String(45), default='')
    jbof_mgmt_username = sa.Column(sa.String(120))
    jbof_mgmt_password = sa.Column(sa.EncryptedText())


class JBOFService(CRUDService):

    class Config:
        service = 'jbof'
        datastore = 'storage.jbof'
        datastore_prefix = "jbof_"
        cli_private = True

    ENTRY = Dict(
        'jbof_entry',
        Int('id', required=True),

        Str('description'),

        # Redfish
        IPAddr('mgmt_ip1', required=True),
        IPAddr('mgmt_ip2', required=False),
        Str('mgmt_username', required=True),
        Password('mgmt_password', required=True),
    )

    @private
    async def add_index(self, data):
        """Add a private unique index (0-255) to the entry if not already present."""
        if 'index' not in data:
            index = await self.middleware.call('jbof.next_index')
            if index is not None:
                data['index'] = index
        return data

    @private
    async def validate(self, data, schema_name, old=None):
        verrors = ValidationErrors()

        # Check license
        license_count = await self.middleware.call("jbof.licensed")
        if license_count == 0:
            verrors.add(f"{schema_name}.mgmt_ip1", "This feature is not licensed")
        else:
            if old is None:
                # We're adding a new JBOF - have we exceeded the license?
                count = await self.middleware.call('jbof.query', [], {'count': True})
                if count >= license_count:
                    verrors.add(f"{schema_name}.mgmt_ip1", f"Already configured the number of licensed emclosures: {license_count}")

        # Ensure redfish connects to mgmt1 (incl login)
        mgmt_ip1 = data.get('mgmt_ip1')
        if not RedfishClient.is_redfish(mgmt_ip1):
            verrors.add(f"{schema_name}.mgmt_ip1", "Not a redfish management interface")
        else:
            redfish1 = RedfishClient(f'https://{mgmt_ip1}')
            try:
                redfish1.login(data['mgmt_username'], data['mgmt_password'])
                RedfishClient.cache_set(mgmt_ip1, redfish1)
            except InvalidCredentialsError:
                verrors.add(f"{schema_name}.mgmt_username", "Invalid username or password")

        # If mgmt_ip2 was supplied, ensure it matches to the same system as mgmt_ip1
        mgmt_ip2 = data.get('mgmt_ip2')
        if mgmt_ip2:
            if not RedfishClient.is_redfish(mgmt_ip2):
                verrors.add(f"{schema_name}.mgmt_ip2", "Not a redfish management interface")
            else:
                redfish2 = RedfishClient(f'https://{mgmt_ip2}')
                if redfish1.product != redfish2.product:
                    verrors.add(f"{schema_name}.mgmt_ip2", "Product does not match other IP address.")
                if redfish1.uuid != redfish2.uuid:
                    verrors.add(f"{schema_name}.mgmt_ip2", "UUID does not match other IP address.")

        # When adding a new JBOF - do we have a UUID clash?
        if old is None:
            existing_uuids = [d['uuid'] for d in (await self.middleware.call('jbof.query', [], {'select': ['uuid']}))]
            if redfish1.uuid in existing_uuids:
                verrors.add(f"{schema_name}.mgmt_ip1", "Supplied JBOF already in database (UUID)")
            else:
                # Inject UUID
                data['uuid'] = redfish1.uuid

        await self.add_index(data)
        return verrors, data

    @accepts(
        Patch(
            'jbof_entry', 'jbof_create',
            ('rm', {'name': 'id'}),
            register=True
        )
    )
    async def do_create(self, data):
        """
        Create a new JBOF.

        This will use the supplied Redfish credentials to configure the data plane on
        the expansion shelf for direct connection to ROCE capable network cards on
        the TrueNAS head unit.

        `description` Optional description of the JBOF.

        `mgmt_ip1` IP of 1st Redfish management interface.

        `mgmt_ip2` Optional IP of 2nd Redfish management interface.

        `mgmt_username` Redfish administrative username.

        `mgmt_password` Redfish administrative password.
        """
        verrors, data = await self.validate(data, 'jbof_create')
        verrors.check()

        mgmt_ip = data['mgmt_ip1']
        shelf_index = data['index']

        # Everything looks good so far.  Attempt to hardwire the dataplane.
        try:
            await self.middleware.call('jbof.hardwire_dataplane', mgmt_ip, shelf_index, 'jbof_create.mgmt_ip1', verrors)
            if verrors:
                await self.middleware.call('jbof.unwire_dataplane', mgmt_ip, shelf_index)
        except Exception as e:
            self.logger.error('Failed to add JBOF', exc_info=True)
            # Try a cleanup
            try:
                await self.middleware.call('jbof.unwire_dataplane', mgmt_ip, shelf_index)
            except Exception:
                pass
            verrors.add('jbof_create.mgmt_ip1', f'Failed to add JBOF: {e}')
        verrors.check()

        data['id'] = await self.middleware.call(
            'datastore.insert', self._config.datastore, data,
            {'prefix': self._config.datastore_prefix})

        return await self.get_instance(data['id'])

    @accepts(
        Int('id', required=True),
        Patch(
            'jbof_create', 'jbof_update',
            ('attr', {'update': True})
        )
    )
    async def do_update(self, id_, data):
        """
        Update JBOF of `id`
        """
        old = await self.get_instance(id_)
        new = old.copy()
        new.update(data)
        verrors, data = await self.validate(new, 'jbof_update', old)
        verrors.check()

        if old['uuid'] != new['uuid']:
            self.middleware.logger.debug('Changed UUID of JBOF')
            await self.middleware.call('jbof.unwire_dataplane', old['mgmt_ip1'], old['index'])
            await self.middleware.call('jbof.hardwire_dataplane', new['mgmt_ip1'], new['index'], 'jbof_update.mgmt_ip1', verrors)

        await self.middleware.call(
            'datastore.update', self._config.datastore, id_, new,
            {'prefix': self._config.datastore_prefix})

        return await self.get_instance(id_)

    @accepts(Int('id'))
    async def do_delete(self, id_):
        """
        Delete a JBOF by ID.
        """
        # Will make a best-effort un tear down existing connections / wiring
        # To do that we first need to fetch the config.
        data = await self.get_instance(id_)
        await self.middleware.run_in_thread(self.ensure_redfish_client_cached,
                                            data['mgmt_ip1'],
                                            data.get('mgmt_username'),
                                            data.get('mgmt_password'))
        try:
            await self.middleware.call('jbof.unwire_dataplane', data['mgmt_ip1'], data['index'])
        except Exception:
            self.middleware.logger.debug('Unable to unwire JBOF @%r', data['mgmt_ip1'])

        # Now delete the entry
        response = await self.middleware.call('datastore.delete', self._config.datastore, id_)
        # await self.middleware.call('service.restart', 'ntpd')
        return response

    @private
    def ensure_redfish_client_cached(self, mgmt_ip, username=None, password=None):
        """Synchronous function to ensure we have a redfish client in cache."""
        try:
            RedfishClient.cache_get(self.middleware, mgmt_ip)
        except KeyError:
            # This could take a while to login, etc ... hence synchronous wrapper.
            redfish = RedfishClient(f'https://{mgmt_ip}', username, password)
            RedfishClient.cache_set(mgmt_ip, redfish)

    @private
    async def licensed(self):
        """Return a count of the number of JBOF units licensed"""
        result = 0
        # Do we have a license at all?
        license_ = await self.middleware.call('system.license')
        if not license_:
            return result

        # check if this node's system serial matches the serial in the license
        local_serial = (await self.middleware.call('system.dmidecode_info'))['system-serial-number']
        if local_serial not in (license_['system_serial'], license_['system_serial_ha']):
            return result

        # Check to see if we're licensed to attach a JBOF
        if license_['addhw']:
            for quantity, code in license_['addhw']:
                if code not in LICENSE_ADDHW_MAPPING:
                    self.middleware.logger.warning('Unknown additional hardware code %d', code)
                    continue
                name = LICENSE_ADDHW_MAPPING[code]
                if name == 'ES24N':
                    result += quantity
        return result

    @private
    async def next_index(self):
        existing_indices = [d['index'] for d in (await self.middleware.call('jbof.query', [], {'select': ['index']}))]
        for index in range(0, 256):
            if index not in existing_indices:
                break
        if index not in existing_indices:
            return index

    @private
    async def hardwire_dataplane(self, mgmt_ip, shelf_index, schema, verrors):
        """Hardware the dataplane interfaces of the specified JBOF.

        Configure the data plane network interfaces on the JBOF to
        previously determined subnets.

        Then attempt to connect using all the available RDMA capable
        interfaces.
        """
        # shelf_interfaces = await self.middleware.call('jbof.fabric_interface_choices', mgmt_ip)
        await self.middleware.call('jbof.hardwire_shelf', mgmt_ip, shelf_index)
        await self.middleware.call('jbof.hardwire_host', mgmt_ip, shelf_index, schema, verrors)

    @private
    def fabric_interface_choices(self, mgmt_ip):
        redfish = RedfishClient.cache_get(self.middleware, mgmt_ip)
        return redfish.fabric_ethernet_interfaces()

    @private
    def fabric_interface_macs(self, mgmt_ip):
        """Return a dict keyed by IP address where the value is the corresponding MAC address."""
        redfish = RedfishClient.cache_get(self.middleware, mgmt_ip)
        macs = {}
        for uri in self.fabric_interface_choices(mgmt_ip):
            netdata = redfish.get_uri(uri)
            for address in netdata['IPv4Addresses']:
                macs[address['Address']] = netdata['MACAddress']
        return macs

    @private
    def hardwire_shelf(self, mgmt_ip, shelf_index):
        redfish = RedfishClient.cache_get(self.middleware, mgmt_ip)
        shelf_interfaces = redfish.fabric_ethernet_interfaces()
        for (eth_index, uri) in enumerate(shelf_interfaces):
            address = jbof_static_ip(shelf_index, eth_index)
            redfish.configure_fabric_interface(uri, address, static_ip_netmask_str(address), mtusize=static_mtu())

    @private
    def unwire_shelf(self, mgmt_ip):
        redfish = RedfishClient.cache_get(self.middleware, mgmt_ip)
        for uri in redfish.fabric_ethernet_interfaces():
            redfish.configure_fabric_interface(uri, '0.0.0.0', '255.255.255.0', True, mtusize=1500)

    @private
    async def hardwire_host(self, mgmt_ip, shelf_index, schema, verrors):
        """Discover which direct links exist to the specified expansion shelf."""
        # See how many interfaces are available on the expansion shelf
        shelf_interfaces = await self.middleware.call('jbof.fabric_interface_choices', mgmt_ip)
        shelf_ip_to_mac = await self.middleware.call('jbof.fabric_interface_macs', mgmt_ip)
        shelf_ips = list(shelf_ip_to_mac.keys())

        # Setup a dict with the expected IP pairs
        shelf_ip_to_host_ip = {}
        for eth_index in range(0, len(shelf_interfaces)):
            shelf_ip_to_host_ip[jbof_static_ip(shelf_index, eth_index)] = initiator_static_ip(shelf_index, eth_index)

        # Let's check that we have the expected hardwired IPs on the shelf
        if set(shelf_ips) != set(list(shelf_ip_to_host_ip.keys())):
            # This should not happen
            verrors.add(schema, 'JBOF does not have expected IPs.')
            return

        if await self.middleware.call('failover.licensed'):
            # HA system

            if not await self.middleware.call('failover.remote_connected'):
                verrors.add(schema, 'HA system must be in good state to allow configuration.')
                return

            this_node = await self.middleware.call('failover.node')
            if this_node not in ['A', 'B']:
                verrors.add(schema, 'HA system must be in good state to allow configuration: Invalid node')
                return

            for node in ['A', 'B']:
                connected_shelf_ips = await self.hardwire_node(node, shelf_index, shelf_ip_to_mac)
                if not connected_shelf_ips:
                    # Failed to connect any IPs => error
                    verrors.add(schema, 'Must be able to communicate with at least one interface on the expansion shelf.')
                    return
        else:
            connected_shelf_ips = await self.hardwire_node('', shelf_index, shelf_ip_to_mac)
            if not connected_shelf_ips:
                # Failed to connect any IPs => error
                verrors.add(schema, 'Must be able to communicate with at least one interface on the expansion shelf.')
                return

    @private
    async def hardwire_node(self, node, shelf_index, shelf_ip_to_mac):
        localnode = not node or node == await self.middleware.call('failover.node')
        shelf_ips = list(shelf_ip_to_mac.keys())
        # Next see what RDMA-capable links are available on the host
        # Also setup a map for frequent use below
        if localnode:
            links = await self.middleware.call('rdma.get_link_choices')
        else:
            links = await self.middleware.call('failover.call_remote', 'rdma.get_link_choices')

        link_to_netdev = {}
        for link in links:
            link_to_netdev[link['rdma']] = link['netdev']

        # First check to see if any interfaces that were previously configured
        # for this shelf are no longer applicable (they might have been moved to
        # a different port on the JBOF).
        connected_shelf_ips = set()
        dirty = False
        configured_interfaces = await self.middleware.call('rdma.interface.query')
        configured_interface_names = [interface['ifname'] for interface in configured_interfaces]
        for interface in configured_interfaces:
            if node and node != interface['node']:
                continue
            host_ip = interface['address']
            shelf_ip = jbof_static_ip_from_initiator_ip(host_ip)
            netdev = link_to_netdev[interface['ifname']]
            value = decode_static_ip(host_ip)
            if value and value[0] == shelf_index:
                # This is supposed to be connected to our shelf.  Check connectivity.
                if not await self.middleware.call('rdma.interface.ping', node, netdev, shelf_ip, shelf_ip_to_mac[shelf_ip]):
                    # This config looks good, keep it.
                    connected_shelf_ips.add(shelf_ip)
                else:
                    self.logger.info('Removing RDMA interface that cannot connect to JBOF')
                    await self.middleware.call('rdma.interface.delete', interface['id'])
                    dirty = True
        for shelf_ip in shelf_ips:
            if shelf_ip in connected_shelf_ips:
                continue
            # Try each remaining interface
            if dirty:
                configured_interfaces = await self.middleware.call('rdma.interface.query')
                configured_interface_names = [interface['ifname'] for interface in configured_interfaces]
                dirty = False
            for ifname in link_to_netdev.keys():
                if ifname not in configured_interface_names:
                    payload = {
                        'ifname': ifname,
                        'address': initiator_ip_from_jbof_static_ip(shelf_ip),
                        'prefixlen': static_ip_netmask_int(),
                        'mtu': static_mtu(),
                        'check': {'ping_ip': shelf_ip,
                                  'ping_mac': shelf_ip_to_mac[shelf_ip]}
                    }
                    if node:
                        payload['node'] = node
                    if await self.middleware.call('rdma.interface.create', payload):
                        dirty = True
                        connected_shelf_ips.add(shelf_ip)
                        # break out of the ifname loop
                        break
        return list(connected_shelf_ips)

    @private
    async def unwire_host(self, mgmt_ip, shelf_index):
        """Unware the dataplane interfaces of the specified JBOF."""
        # shelf_interfaces = await self.middleware.call('jbof.fabric_interface_choices', mgmt_ip)
        try:
            shelf_interface_count = len(await self.middleware.call('jbof.fabric_interface_choices', mgmt_ip))
        except Exception:
            # Really only expect 4, but we'll over-estimate for now, as we check them anyway
            shelf_interface_count = 6
        possible_host_ips = []
        for eth_index in range(0, shelf_interface_count):
            possible_host_ips.append(initiator_static_ip(shelf_index, eth_index))
        for interface in await self.middleware.call('rdma.interface.query', [['address', 'in', possible_host_ips]]):
            await self.middleware.call('rdma.interface.delete', interface['id'])

    @private
    async def unwire_dataplane(self, mgmt_ip, shelf_index):
        """Unware the dataplane interfaces of the specified JBOF."""
        # shelf_interfaces = await self.middleware.call('jbof.fabric_interface_choices', mgmt_ip)
        await self.middleware.call('jbof.unwire_host', mgmt_ip, shelf_index)
        await self.middleware.call('jbof.unwire_shelf', mgmt_ip)


async def setup(middleware):
    RedfishClient.setup()
