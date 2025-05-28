import asyncio
import os
from contextlib import contextmanager

from spdk import rpc

from middlewared.service import CallError, Service
from middlewared.utils import run
from .constants import NAMESPACE_DEVICE_TYPE, NVMET_DISCOVERY_NQN, PORT_ADDR_FAMILY, PORT_TRTYPE

SETUP_SH = '/opt/spdk/scripts/setup.sh'

SPDK_RPC_SERVER_ADDR = '/var/run/spdk/spdk.sock'
SPDK_RPC_PORT = 5260
SPDK_RPC_TIMEOUT = None
SPDK_RPC_LOG_LEVEL = 'ERROR'
SPDK_RPC_CONN_RETRIES = 0


class NVMetSPDKService(Service):

    class Config:
        private = True
        namespace = 'nvmet.spdk'

    async def _run_setup(self, *args):
        command = [SETUP_SH, *args]
        cp = await run(command)
        if cp.returncode:
            return False
        return True

    async def setup(self):
        """
        Perform necessary setup for SPDK.

        Allocate hugepages and bind PCI devices.
        """
        _slots = await self.slots()
        return await self._run_setup('config', f'PCI_ALLOWED="{" ".join(_slots)}"')

    async def reset(self):
        """
        Rebind PCI devices back to their original drivers.

        Also cleanup any leftover spdk files/resources.
        Hugepage memory size will remain unchanged.
        """
        return await self._run_setup('reset')

    async def cleanup(self):
        """
        Remove any orphaned files that can be left in the system after SPDK application exit
        """
        return await self._run_setup('cleanup')

    async def slots(self):
        _nics = await self.nics()
        return await self.middleware.call('nvmet.spdk.pci_slots', _nics)

    def pci_slots(self, nics):
        pci_slots = []
        for nic in nics:
            with open(f'/sys/class/net/{nic}/device/uevent', 'r') as f:
                for line in f:
                    if line.startswith('PCI_SLOT_NAME='):
                        if slot := line.strip().split('=', 1)[1]:
                            pci_slots.append(slot)
                            break
        if len(nics) != len(pci_slots):
            raise CallError("Could not find PCI slot for every NIC")
        return pci_slots

    async def nics(self):
        """
        Return a list of NIC names correesponding to all configure NVMe-oF ports.
        """
        # Check that kernel nvmet is not enabled
        if (await self.middleware.call('nvmet.global.config'))['kernel']:
            raise CallError("NVMe-oF configured for kernel target")

        # Need to obtain the PCI devices associated with configured ports
        ports = await self.middleware.call('nvmet.port.query')
        if not ports:
            raise CallError("No ports configured for NVMe-oF")

        # For the time being we only support TCP/RDMA with IPv6/IPv6
        addresses = set()
        for port in ports:
            if port['addr_trtype'] not in [PORT_TRTYPE.TCP.api, PORT_TRTYPE.RDMA.api]:
                raise CallError(f"Unsupported addr_trtype: {port['addr_trtype']!r}")
            if port['addr_adrfam'] not in [PORT_ADDR_FAMILY.IPV4.api, PORT_ADDR_FAMILY.IPV6.api]:
                raise CallError(f"Unsupported addr_adrfam: {port['addr_adrfam']!r}")
            addresses.add(port['addr_traddr'])

        if not addresses:
            raise CallError("No IP addresses configured for NVMe-oF")

        # Now query the interfaces to discover which ones are being used
        nics = []
        iface_filter = [['OR', [
            ['state.aliases.*.address', 'in', addresses],
            ['state.failover_virtual_aliases.*.address', 'in', addresses]
        ]]]
        interfaces = await self.middleware.call('interface.query', iface_filter)
        for address in addresses:
            name = self._address_to_iface_name(address, interfaces)
            if not name:
                raise CallError(f"Could not find interface for address: {address}")
            nics.append(name)

        return nics

    def _address_to_iface_name(self, address, interfaces):
        for iface in interfaces:
            for alias in iface.get('state', {}).get('aliases', []):
                if alias.get('address') == address:
                    return iface['name']
            for alias in iface.get('state', {}).get('failover_virtual_aliases', []):
                if alias.get('address') == address:
                    return iface['name']

    def nvmf_ready(self, cheap=False):
        if os.path.exists(SPDK_RPC_SERVER_ADDR):
            if cheap:
                return True
            try:
                client = make_client()
                rpc.framework_wait_init(client)
                return True
            except Exception:
                pass
        return False

    async def wait_nvmf_ready(self, retries=10):
        while retries > 0:
            if await self.middleware.call('nvmet.spdk.nvmf_ready'):
                return True
            await asyncio.sleep(1)
            retries -= 1
        return False


class NvmetConfig:

    def config_key(self, config_item):
        return str(config_item[self.query_key])

    def config_dict(self, render_ctx):
        return {self.config_key(entry): entry for entry in render_ctx[self.query]}

    @contextmanager
    def render(self, client, render_ctx: dict):
        live = self.get_live(client, render_ctx)
        config = self.config_dict(render_ctx)
        config_keys = set(config.keys())
        live_keys = set(live.keys())
        add_keys = config_keys - live_keys
        remove_keys = live_keys - config_keys
        remove_keys.discard(NVMET_DISCOVERY_NQN)
        update_keys = config_keys - remove_keys - add_keys

        for item in add_keys:
            self.add(client, config[item], render_ctx)

        for item in update_keys:
            self.update(client, config[item], live[item], render_ctx)

        yield

        for item in remove_keys:
            self.delete(client, live[item], render_ctx)


class NvmetSubsysConfig(NvmetConfig):
    query = 'nvmet.subsys.query'
    query_key = 'subnqn'

    def get_live(self, client, render_ctx):
        return {subsys['nqn']: subsys for subsys in rpc.nvmf.nvmf_get_subsystems(client)}

    def add(self, client, config_item, render_ctx):

        kwargs = {
            'nqn': config_item['subnqn'],
            'serial_number': config_item['serial'],
            'allow_any_host': config_item['allow_any_host'],
            'model_number': render_ctx['nvmet.subsys.model'],
        }

        # Perhaps inject some values
        match render_ctx['failover.node']:
            case 'A':
                kwargs['max_cntlid'] = 31999
            case 'B':
                kwargs['min_cntlid'] = 32000

        rpc.nvmf.nvmf_create_subsystem(client, **kwargs)

    def update(self, client, config_item, live_item, render_ctx):
        if config_item['allow_any_host'] != live_item['allow_any_host']:
            # The wrapper function inverts the parameter, so use NOT
            rpc.nvmf.nvmf_subsystem_allow_any_host(client, config_item['subnqn'], not config_item['allow_any_host'])

    def delete(self, client, live_item, render_ctx):
        rpc.nvmf.nvmf_delete_subsystem(client, nqn=live_item['nqn'])


class NvmetTransportConfig:
    """
    There currently is no mechanism to unload transports, so in the render
    we will simply add them if necessary.
    """
    @contextmanager
    def render(self, client, render_ctx: dict):
        # Create a set of the transports demanded by the config
        required = set([port['addr_trtype'] for port in render_ctx['nvmet.port.query']])
        current = set([transport['trtype'] for transport in rpc.nvmf.nvmf_get_transports(client)])
        for transport in required - current:
            rpc.nvmf.nvmf_create_transport(client, trtype=transport)
        yield


class NvmetPortConfig(NvmetConfig):
    """
    SPDK doesn't have a seperate definition of ports, listeners are attached to
    subsystems.  We will model this by attaching listeners to the discovery port
    for the port config, and use port_subsys for other subsystems.
    """
    query = 'nvmet.port.query'
    query_key = 'subnqn'

    def config_key(self, config_item):
        match config_item['addr_adrfam']:
            case PORT_ADDR_FAMILY.IPV4.api | PORT_ADDR_FAMILY.IPV6.api:
                return f"{config_item['addr_trtype']}:{config_item['addr_traddr']}:{config_item['addr_trsvcid']}"
            case _:
                # Keep a trailing colon here to simply logic that depends on split()
                return f"{config_item['addr_trtype']}:{config_item['addr_traddr']}:"

    def live_address_to_key(self, laddr):
        match laddr['trtype']:
            case 'RDMA' | 'TCP':
                return f"{laddr['trtype']}:{laddr['traddr']}:{laddr['trsvcid']}"
            case _:
                # Keep a trailing colon here to simply logic that depends on split()
                return f"{laddr['trtype']}:{laddr['traddr']}:"

    def live_key(self, live_item):
        return self.live_address_to_key(live_item['address'])

    def get_live(self, client, render_ctx):
        return {self.live_key(entry): entry for entry in
                rpc.nvmf.nvmf_subsystem_get_listeners(client, nqn=NVMET_DISCOVERY_NQN)}

    def add_to_nqn(self, client, config_item, nqn, render_ctx):
        kwargs = {
            'nqn': nqn,
            'trtype': config_item['addr_trtype'],
            'adrfam': PORT_ADDR_FAMILY.by_api(config_item['addr_adrfam']).spdk,
            'traddr': config_item['addr_traddr'],
            'trsvcid': str(config_item['addr_trsvcid'])
        }
        # The API will generate the listen_address from its constituents - hence flat here
        rpc.nvmf.nvmf_subsystem_add_listener(client, **kwargs)

    def add(self, client, config_item, render_ctx):
        self.add_to_nqn(client, config_item, NVMET_DISCOVERY_NQN, render_ctx)

    def update(self, client, config_item, live_item, render_ctx):
        # We cannot update a listener, but no real need because all the beef is
        # in the key.  If something changes there we'll get a remove and add
        # instead.
        pass

    def delete_from_nqn(self, client, laddr, nqn, render_ctx):
        kwargs = {
            'nqn': nqn,
        }
        kwargs.update(laddr)
        rpc.nvmf.nvmf_subsystem_remove_listener(client, **kwargs)

    def delete(self, client, live_item, render_ctx):
        self.delete_from_nqn(client, live_item['address'], NVMET_DISCOVERY_NQN, render_ctx)


class NvmetPortSubsysConfig(NvmetPortConfig):
    query = 'nvmet.port_subsys.query'

    def config_key(self, config_item):
        return f"{super().config_key(config_item['port'])}:{config_item['subsys']['subnqn']}"

    def get_live(self, client, render_ctx):
        result = {}
        for subsys in rpc.nvmf.nvmf_get_subsystems(client):
            if subsys['nqn'] == NVMET_DISCOVERY_NQN:
                continue
            for address in subsys['listen_addresses']:
                port_key = self.live_address_to_key(address)
                # Construct a synthetic live item that will facilitate delete when needed
                result[f"{port_key}:{subsys['nqn']}"] = {'port': address, 'nqn': subsys['nqn']}
        return result

    def add(self, client, config_item, render_ctx):
        self.add_to_nqn(client, config_item['port'], config_item['subsys']['subnqn'], render_ctx)

    def delete(self, client, live_item, render_ctx):
        self.delete_from_nqn(client, live_item['port'], live_item['nqn'], render_ctx)


class NvmetBdevConfig(NvmetPortConfig):
    query = 'nvmet.namespace.query'

    def config_key(self, config_item):
        return f"{config_item['device_type']}:{config_item['device_path']}"

    def live_key(self, live_item):
        match live_item['product_name']:
            case 'URING bdev':
                if filename := live_item.get('driver_specific', {}).get('uring', {}).get('filename'):
                    if filename.startswith('/dev/zvol/'):
                        return f'ZVOL:{filename[5:]}'
            case 'AIO disk':
                if filename := live_item.get('driver_specific', {}).get('aio', {}).get('filename'):
                    if filename.startswith('/mnt'):
                        return f'FILE:{filename}'

    def get_live(self, client, render_ctx):
        result = {}
        for entry in rpc.bdev.bdev_get_bdevs(client):
            if key := self.live_key(entry):
                result[key] = entry
        return result

    def bdev_name(self, config_item):
        match config_item['device_type']:
            case NAMESPACE_DEVICE_TYPE.ZVOL.api:
                return f"ZVOL:{config_item['device_path']}"

            case NAMESPACE_DEVICE_TYPE.FILE.api:
                return f"FILE:{config_item['device_path']}"

    def add(self, client, config_item, render_ctx):
        name = self.bdev_name(config_item)
        if not name:
            return
        match config_item['device_type']:
            case NAMESPACE_DEVICE_TYPE.ZVOL.api:
                rpc.bdev.bdev_uring_create(client,
                                           filename=f"/dev/{config_item['device_path']}",
                                           name=name
                                           )

            case NAMESPACE_DEVICE_TYPE.FILE.api:
                rpc.bdev.bdev_aio_create(client,
                                         filename=config_item['device_path'],
                                         name=name
                                         )

    def update(self, client, config_item, live_item, render_ctx):
        pass

    def delete(self, client, live_item, render_ctx):
        match live_item['product_name']:
            case 'URING bdev':
                rpc.bdev.bdev_uring_delete(client, name=live_item['name'])

            case 'AIO disk':
                rpc.bdev.bdev_aio_delete(client, name=live_item['name'])


class NvmetNamespaceConfig(NvmetBdevConfig):
    query = 'nvmet.namespace.query'

    def config_key(self, config_item):
        name = self.bdev_name(config_item)
        return f"{name}:{config_item['subsys']['subnqn']}:{config_item['nsid']}"

    def get_live(self, client, render_ctx):
        result = {}
        for subsys in rpc.nvmf.nvmf_get_subsystems(client):
            _nqn = subsys['nqn']
            for ns in subsys.get('namespaces', []):
                _nsid = ns['nsid']
                key = f"{ns['bdev_name']}:{_nqn}:{_nsid}"
                result[key] = {'nqn': _nqn, 'nsid': _nsid}
        return result

    def add(self, client, config_item, render_ctx):
        name = self.bdev_name(config_item)
        if not name:
            return
        kwargs = {
            'nqn': config_item['subsys']['subnqn'],
            'bdev_name': name,
            'uuid': config_item['device_uuid'],
            'nguid': config_item['device_nguid'].replace('-', ''),
        }
        if nsid := config_item.get('nsid'):
            kwargs.update({'nsid': nsid})
        # anagrpid
        rpc.nvmf.nvmf_subsystem_add_ns(client, **kwargs)

    def delete(self, client, live_item, render_ctx):
        kwargs = {
            'nqn': live_item['nqn'],
            'nsid': live_item['nsid']
        }
        rpc.nvmf.nvmf_subsystem_remove_ns(client, **kwargs)


def make_client():
    return rpc.client.JSONRPCClient(SPDK_RPC_SERVER_ADDR,
                                    SPDK_RPC_PORT,
                                    SPDK_RPC_TIMEOUT,
                                    log_level=SPDK_RPC_LOG_LEVEL,
                                    conn_retries=SPDK_RPC_CONN_RETRIES)


def write_config(config):
    client = make_client()

    # Render operations are context managers that do
    # 1. Create-style operations
    # 2. yield
    # 3. Delete-style operations
    #
    # Therefore we can nest them to enfore the necessary
    # order of operations.
    with (
        NvmetSubsysConfig().render(client, config),
        NvmetTransportConfig().render(client, config),
        # NvmetHostConfig().render(config),
        NvmetPortConfig().render(client, config),
        # NvmetPortReferralConfig().render(config),
        # NvmetPortAnaReferralConfig().render(config),
        # NvmetHostSubsysConfig().render(config),
        NvmetPortSubsysConfig().render(client, config),
        NvmetBdevConfig().render(client, config),
        NvmetNamespaceConfig().render(client, config),
    ):
        pass
