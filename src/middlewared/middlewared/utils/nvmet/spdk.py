import copy
import hashlib
import os
import tempfile
from contextlib import contextmanager

from spdk import rpc

from middlewared.plugins.nvmet.constants import (NAMESPACE_DEVICE_TYPE,
                                                 NVMET_DISCOVERY_NQN,
                                                 PORT_ADDR_FAMILY)
from .render_common import (ANA_INACCESSIBLE_STATE,
                            ANA_OPTIMIZED_STATE,
                            ANA_PORT_INDEX_OFFSET,
                            NVMET_NODE_A_MAX_CONTROLLER_ID,
                            NVMET_NODE_B_MIN_CONTROLLER_ID,
                            addr_traddr_to_address,
                            ana_grpid,
                            ana_state,
                            port_subsys_index,
                            subsys_ana,
                            subsys_visible)

SPDK_RPC_SERVER_ADDR = '/var/run/spdk/spdk.sock'
SPDK_RPC_PORT = 5260
SPDK_RPC_TIMEOUT = None
SPDK_RPC_LOG_LEVEL = 'ERROR'
SPDK_RPC_CONN_RETRIES = 0

# Directory into which we will place our keys
SPDK_KEY_DIR = '/var/run/spdk/keys'


def host_config_key(config_item, key_type):
    if key_value := config_item[key_type]:
        md5_hash = hashlib.md5()
        md5_hash.update(key_value.encode('utf-8'))
        # Colon confuses things, replace
        return f'{key_type}-{config_item["hostnqn"].replace(":", "-")}-{md5_hash.hexdigest()}'


def nvmf_ready(cheap=False):
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


class NvmetConfig:
    DEBUG = False

    def config_key(self, config_item, render_ctx):
        return str(config_item[self.query_key])

    def config_dict(self, render_ctx):
        # Implement so that any class can skip entries by returning
        # a config_key of None
        result = {}
        for entry in render_ctx[self.query]:
            if (key := self.config_key(entry, render_ctx)) is not None:
                result[key] = entry
        return result

    def debug_title(self, title):
        outstr = f'{title} ({self.__class__.__name__})'
        print(outstr)
        print('=' * len(outstr))

    def debug(self, live, config):
        if self.DEBUG:
            import pprint
            self.debug_title('LIVE')
            pprint.pprint(live)
            print()

            self.debug_title('CONFIG')
            pprint.pprint(config)
            print()

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

        self.debug(live, config)

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

    def config_key(self, config_item, render_ctx):
        if subsys_visible(config_item, render_ctx):
            return str(config_item[self.query_key])

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
                kwargs['max_cntlid'] = NVMET_NODE_A_MAX_CONTROLLER_ID
            case 'B':
                kwargs['min_cntlid'] = NVMET_NODE_B_MIN_CONTROLLER_ID

        if render_ctx['failover.licensed']:
            kwargs['ana_reporting'] = True

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

    def config_dict(self, render_ctx):
        # For ports we may want to inject or remove ports wrt the ANA
        # settings.  ANA ports will be offset by ANA_PORT_INDEX_OFFSET (5000).
        config = {}
        non_ana_port_ids = render_ctx['nvmet.port.usage']['non_ana_port_ids']
        ana_port_ids = render_ctx['nvmet.port.usage']['ana_port_ids']
        for entry in render_ctx[self.query]:
            port_id = entry['id']
            if port_id in non_ana_port_ids:
                config[str(entry['index'])] = entry
            if port_id in ana_port_ids:
                new_index = ANA_PORT_INDEX_OFFSET + entry['index']
                config[str(new_index)] = entry | {'index': new_index}
        return config

    def live_to_index(self, addr_trtype, addr_traddr, addr_trsvcid, render_ctx):
        for entry in render_ctx['nvmet.port.query']:
            if addr_trtype != entry['addr_trtype'] or str(addr_trsvcid) != str(entry['addr_trsvcid']):
                continue
            elif addr_traddr == entry['addr_traddr']:
                return str(entry['index'])
            elif addr_traddr == addr_traddr_to_address(entry['index'] + ANA_PORT_INDEX_OFFSET,
                                                       entry['addr_trtype'],
                                                       entry['addr_traddr'],
                                                       render_ctx):
                return str(entry['index'] + ANA_PORT_INDEX_OFFSET)

    def live_address_to_key(self, laddr, render_ctx):
        if index := self.live_to_index(laddr['trtype'], laddr['traddr'], laddr['trsvcid'], render_ctx):
            return index
        else:
            match laddr['trtype']:
                case 'RDMA' | 'TCP':
                    return f"{laddr['trtype']}:{laddr['traddr']}:{laddr['trsvcid']}"
                case _:
                    # Keep a trailing colon here to simply logic that depends on split()
                    return f"{laddr['trtype']}:{laddr['traddr']}:"

    def config_key(self, config_item, render_ctx):
        return config_item['index']

    def get_live(self, client, render_ctx):
        return {self.live_address_to_key(entry['address'], render_ctx): entry
                for entry in rpc.nvmf.nvmf_subsystem_get_listeners(client, nqn=NVMET_DISCOVERY_NQN)}

    def add_to_nqn(self, client, config_item, nqn, render_ctx):
        kwargs = {
            'nqn': nqn,
            'trtype': config_item['addr_trtype'],
            'adrfam': PORT_ADDR_FAMILY.by_api(config_item['addr_adrfam']).spdk,
            'traddr': addr_traddr_to_address(config_item['index'],
                                             config_item['addr_trtype'],
                                             config_item['addr_traddr'],
                                             render_ctx),
            'trsvcid': str(config_item['addr_trsvcid'])
        }
        # The API will generate the listen_address from its constituents - hence flat here
        rpc.nvmf.nvmf_subsystem_add_listener(client, **kwargs)

        if nqn != NVMET_DISCOVERY_NQN and config_item['index'] > ANA_PORT_INDEX_OFFSET:
            kwargs['ana_state'] = ana_state(render_ctx)
            kwargs.update({'anagrpid': ana_grpid(render_ctx)})
            rpc.nvmf.nvmf_subsystem_listener_set_ana_state(client, **kwargs)

    def add(self, client, config_item, render_ctx):
        self.add_to_nqn(client, config_item, NVMET_DISCOVERY_NQN, render_ctx)

    def address_match(self, config_item, live_address):
        if config_item['addr_trtype'] != live_address['trtype'] or \
           config_item['addr_traddr'] != live_address['traddr'] or \
           str(config_item['addr_trsvcid']) != live_address['trsvcid']:
            return False
        return True

    def update(self, client, config_item, live_item, render_ctx):
        if not self.address_match(config_item, live_item['address']):
            self.delete(client, live_item, render_ctx)
            self.add(client, config_item, render_ctx)

    def delete_from_nqn(self, client, laddr, nqn, render_ctx):
        kwargs = {
            'nqn': nqn,
        }
        kwargs.update(laddr)
        rpc.nvmf.nvmf_subsystem_remove_listener(client, **kwargs)

    def delete(self, client, live_item, render_ctx):
        self.delete_from_nqn(client, live_item['address'], NVMET_DISCOVERY_NQN, render_ctx)


class NvmetPortAnaReferralConfig(NvmetConfig):
    """
    Referrals are substantially different in SPDK than in the kernel
    implementation.  They are global rather than attached to a
    particular port.

    Therefore we will just add referrals for each ANA port to its peer.
    """
    query = 'nvmet.port.query'

    def config_dict(self, render_ctx):
        config = {}
        # If not HA then no peer referrals
        if render_ctx['failover.node'] not in ('A', 'B'):
            return config

        # If ANA is enabled on a port then we want to add a referral to
        # the peer port on the other node.
        ana_port_ids = render_ctx['nvmet.port.usage']['ana_port_ids']
        for entry in render_ctx[self.query]:
            port_id = entry['id']
            if port_id in ana_port_ids:
                peer_addr = None
                prefix = entry['addr_trtype'].lower()
                choices = render_ctx[f'{prefix}.nvmet.port.transport_address_choices']
                try:
                    pair = choices[entry['addr_traddr']].split('/')
                except KeyError:
                    continue
                match render_ctx['failover.node']:
                    case 'A':
                        peer_addr = pair[1]
                    case 'B':
                        peer_addr = pair[0]
                if peer_addr:
                    # Make the entry a valid listen address to simplify implementation of add()
                    config[f"{entry['addr_trtype']}:{peer_addr}:{entry['addr_trsvcid']}"] = {
                        'trtype': entry['addr_trtype'],
                        'adrfam': PORT_ADDR_FAMILY.by_api(entry['addr_adrfam']).spdk,
                        'traddr': peer_addr,
                        'trsvcid': str(entry['addr_trsvcid']),
                    }
        return config

    def add(self, client, config_item, render_ctx):
        rpc.nvmf.nvmf_discovery_add_referral(client, **config_item)

    def update(self, client, config_item, live_item, render_ctx):
        # Update is a no-op because all the relevant data is in the key
        pass

    def delete(self, client, live_item, render_ctx):
        rpc.nvmf.nvmf_discovery_remove_referral(client, **live_item)
        pass

    def get_live(self, client, render_ctx):
        result = {}
        for entry in rpc.nvmf.nvmf_discovery_get_referrals(client):
            laddr = entry['address']
            result[f"{laddr['trtype']}:{laddr['traddr']}:{laddr['trsvcid']}"] = laddr
        return result


class NvmetPortSubsysConfig(NvmetPortConfig):
    query = 'nvmet.port_subsys.query'

    def config_dict(self, render_ctx):
        # For ports we may want to inject or remove ports wrt the ANA
        # settings.  ANA ports will be offset by ANA_PORT_INDEX_OFFSET (5000).
        #
        # For the general port setting we could use nvmet.port.usage, but
        # per subsystem we need to be more specific.
        config = {}
        for entry in render_ctx[self.query]:
            subnqn = entry['subsys']['subnqn']
            if index := port_subsys_index(entry, render_ctx):
                if index < ANA_PORT_INDEX_OFFSET:
                    config[f"{index}:{subnqn}"] = entry
                else:
                    newentry = copy.deepcopy(entry)
                    newentry['port']['index'] = index
                    config[f"{index}:{subnqn}"] = newentry
        return config

    def config_key(self, config_item, render_ctx):
        return f"{super().config_key(config_item['port'], render_ctx)}:{config_item['subsys']['subnqn']}"

    def get_live(self, client, render_ctx):
        result = {}
        for subsys in rpc.nvmf.nvmf_get_subsystems(client):
            if subsys['nqn'] == NVMET_DISCOVERY_NQN:
                continue
            for address in subsys['listen_addresses']:
                port_key = self.live_address_to_key(address, render_ctx)
                # Construct a synthetic live item that will facilitate delete when needed
                result[f"{port_key}:{subsys['nqn']}"] = {'port': address, 'nqn': subsys['nqn']}
        return result

    def add(self, client, config_item, render_ctx):
        self.add_to_nqn(client, config_item['port'], config_item['subsys']['subnqn'], render_ctx)

    def update(self, client, config_item, live_item, render_ctx):
        if not self.address_match(config_item['port'], live_item['port']):
            self.delete(client, live_item, render_ctx)
            self.add(client, config_item, render_ctx)

    def delete(self, client, live_item, render_ctx):
        self.delete_from_nqn(client, live_item['port'], live_item['nqn'], render_ctx)


class NvmetKeyringDhchapKeyConfig(NvmetConfig):
    """
    We may have configured dhchap_key or dhchap_ctrl_key for each host.

    Both will be derived from nvmet.host.query, but in different
    classes - this one, and a subclass.
    """
    query = 'nvmet.host.query'
    key_type = 'dhchap_key'

    def config_key(self, config_item, render_ctx):
        return host_config_key(config_item, self.key_type)

    def _write_keyfile(self, key):
        with tempfile.NamedTemporaryFile(mode="w+", dir=SPDK_KEY_DIR, delete=False) as tmp_file:
            tmp_file.write(key)
            return tmp_file.name

    def get_live(self, client, render_ctx):
        return {item['name']: item for item in rpc.keyring.keyring_get_keys(client)
                if item['name'].startswith(f'{self.key_type}-')}

    def add(self, client, config_item, render_ctx):
        kwargs = {
            'name': self.config_key(config_item, render_ctx),
            'path': self._write_keyfile(config_item[self.key_type]),
        }
        rpc.keyring.keyring_file_add_key(client, **kwargs)

    def update(self, client, config_item, live_item, render_ctx):
        # Because the key contains a hash, we only need to handle add and remove.
        pass

    def delete(self, client, live_item, render_ctx):
        rpc.keyring.keyring_file_remove_key(client, name=live_item['name'])
        os.unlink(live_item['path'])


class NvmetKeyringDhchapCtrlKeyConfig(NvmetKeyringDhchapKeyConfig):
    query = 'nvmet.host.query'
    key_type = 'dhchap_ctrl_key'


class NvmetHostSubsysConfig(NvmetConfig):
    query = 'nvmet.host_subsys.query'

    def config_key(self, config_item, render_ctx):

        return f"{config_item['host']['hostnqn']}:{config_item['subsys']['subnqn']}"

    def get_live(self, client, render_ctx):
        result = {}
        for subsys in rpc.nvmf.nvmf_get_subsystems(client):
            if subsys['nqn'] == NVMET_DISCOVERY_NQN:
                continue
            for host in subsys['hosts']:
                hostnqn = host['nqn']
                # Yes, deliberately mapped live dhchap_ctrlr_key to dhchap_ctrl_key here to
                # make comparison in the update method easier
                result[f"{hostnqn}:{subsys['nqn']}"] = {'hostnqn': hostnqn,
                                                        'nqn': subsys['nqn'],
                                                        'dhchap_key': host.get('dhchap_key'),
                                                        'dhchap_ctrl_key': host.get('dhchap_ctrlr_key'),
                                                        }
        return result

    def add(self, client, config_item, render_ctx):
        kwargs = {
            'nqn': config_item['subsys']['subnqn'],
            'host': config_item['host']['hostnqn'],
        }

        if config_item['host']['dhchap_key']:
            kwargs.update({'dhchap_key': host_config_key(config_item['host'], 'dhchap_key')})

        if config_item['host']['dhchap_ctrl_key']:
            # Yes, the SPDK name is different from the name in our config:
            # dhchap_ctrlr_key vs dhchap_ctrl_key
            kwargs.update({'dhchap_ctrlr_key': host_config_key(config_item['host'], 'dhchap_ctrl_key')})

        # If this is a HA system then inject some settings
        match render_ctx['failover.node']:
            case 'A':
                kwargs.update({'max_cntlid': NVMET_NODE_A_MAX_CONTROLLER_ID})
            case 'B':
                kwargs.update({'min_cntlid': NVMET_NODE_B_MIN_CONTROLLER_ID})

        rpc.nvmf.nvmf_subsystem_add_host(client, **kwargs)

    def update(self, client, config_item, live_item, render_ctx):
        # We cannot update, so need to remove and reattach if the contents are wrong.
        config_host = config_item['host']
        matches = True
        for key_type in ('dhchap_key', 'dhchap_ctrl_key'):
            if config_host[key_type] is None and live_item[key_type] is None:
                continue
            if config_host[key_type] is None or live_item[key_type] is None:
                matches = False
                break
            if live_item[key_type] != host_config_key(config_host, key_type):
                matches = False
                break

        if matches:
            return

        self.delete(client, live_item, render_ctx)
        self.add(client, config_item, render_ctx)

    def delete(self, client, live_item, render_ctx):
        kwargs = {
            'nqn': live_item['nqn'],
            'host': live_item['hostnqn'],
        }
        rpc.nvmf.nvmf_subsystem_remove_host(client, **kwargs)


class NvmetBdevConfig(NvmetConfig):
    query = 'nvmet.namespace.query'

    def config_key(self, config_item, render_ctx):
        if subsys_visible(config_item['subsys'], render_ctx):
            if render_ctx['failover.status'] != 'BACKUP':
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
            case 'Null disk':
                return live_item['name']

    def get_live(self, client, render_ctx):
        result = {}
        for entry in rpc.bdev.bdev_get_bdevs(client):
            if key := self.live_key(entry):
                result[key] = entry
        return result

    def bdev_name(self, config_item, render_ctx):
        # Skip is we're the BACKUP in a HA
        if render_ctx['failover.status'] == 'BACKUP':
            return

        match config_item['device_type']:
            case NAMESPACE_DEVICE_TYPE.ZVOL.api:
                return f"ZVOL:{config_item['device_path']}"

            case NAMESPACE_DEVICE_TYPE.FILE.api:
                return f"FILE:{config_item['device_path']}"

    def add(self, client, config_item, render_ctx):
        name = self.bdev_name(config_item, render_ctx)
        if not name:
            return

        if render_ctx['failover.status'] == 'BACKUP':
            rpc.bdev.bdev_null_create(client,
                                      block_size=4096,
                                      num_blocks=1,
                                      name=name
                                      )
            return

        match config_item['device_type']:
            case NAMESPACE_DEVICE_TYPE.ZVOL.api:
                rpc.bdev.bdev_uring_create(client,
                                           filename=f"/dev/{config_item['device_path']}",
                                           name=name
                                           )

            case NAMESPACE_DEVICE_TYPE.FILE.api:
                _path = config_item['device_path']
                rpc.bdev.bdev_aio_create(client,
                                         filename=_path,
                                         block_size=render_ctx.get('path_to_recordsize', {}).get(_path, 512),
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

            case 'Null disk':
                rpc.bdev.bdev_null_delete(client, name=live_item['name'])


class NvmetNamespaceConfig(NvmetBdevConfig):
    query = 'nvmet.namespace.query'

    def config_key(self, config_item, render_ctx):
        if subsys_visible(config_item['subsys'], render_ctx):
            name = self.bdev_name(config_item, render_ctx)
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
        name = self.bdev_name(config_item, render_ctx)
        if not name:
            return

        # If HA always use the per-node anagrpid, just to save
        # having to toggle it later if we toggle ANA
        kwargs = {
            'nqn': config_item['subsys']['subnqn'],
            'bdev_name': name,
            'uuid': config_item['device_uuid'],
            'nguid': config_item['device_nguid'].replace('-', ''),
            'anagrpid': ana_grpid(render_ctx),
        }
        if nsid := config_item.get('nsid'):
            kwargs.update({'nsid': nsid})

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


def nvmf_subsystem_get_qpairs(client, nqn):
    return rpc.nvmf.nvmf_subsystem_get_qpairs(client, nqn=nqn)


class NvmetAnaStateConfig:

    @contextmanager
    def render(self, client, render_ctx: dict):
        """
        If we are making things inaccessible then do this before the yield,
        otherwise after the yield.
        """
        new_state = ana_state(render_ctx)
        _anagrpid = ana_grpid(render_ctx)

        updates = []
        for subsys in render_ctx['nvmet.subsys.query']:
            if subsys_ana(subsys, render_ctx):
                nqn = subsys['subnqn']
                for listener in rpc.nvmf.nvmf_subsystem_get_listeners(client, nqn):
                    if cur_state := next(filter(lambda x: x['ana_group'] == _anagrpid, listener['ana_states']), None):
                        if cur_state['ana_state'] != new_state:
                            kwargs = {
                                'nqn': nqn,
                                'ana_state': new_state,
                                'anagrpid': _anagrpid
                            }
                            kwargs.update(listener['address'])
                            updates.append(kwargs)

        if new_state == ANA_INACCESSIBLE_STATE:
            for kwargs in updates:
                rpc.nvmf.nvmf_subsystem_listener_set_ana_state(client, **kwargs)

        yield

        if new_state == ANA_OPTIMIZED_STATE:
            for kwargs in updates:
                rpc.nvmf.nvmf_subsystem_listener_set_ana_state(client, **kwargs)


def write_config(config):
    client = make_client()

    if not os.path.isdir(SPDK_KEY_DIR):
        os.mkdir(SPDK_KEY_DIR)

    # Render operations are context managers that do
    # 1. Create-style operations
    # 2. yield
    # 3. Delete-style operations
    #
    # Therefore we can nest them to enfore the necessary
    # order of operations.
    #
    # SPDK automatically does what we had called cross-port
    # referrals in the kernel implementation.
    with (
        NvmetSubsysConfig().render(client, config),
        NvmetTransportConfig().render(client, config),
        NvmetKeyringDhchapKeyConfig().render(client, config),
        NvmetKeyringDhchapCtrlKeyConfig().render(client, config),
        NvmetPortConfig().render(client, config),
        NvmetPortAnaReferralConfig().render(client, config),
        NvmetHostSubsysConfig().render(client, config),
        NvmetPortSubsysConfig().render(client, config),
        NvmetAnaStateConfig().render(client, config),
        NvmetBdevConfig().render(client, config),
        NvmetNamespaceConfig().render(client, config),
    ):
        pass
