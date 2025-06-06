import os
import pathlib
import subprocess
import time
from collections import defaultdict
from contextlib import contextmanager

from middlewared.plugins.zfs_.utils import zvol_name_to_path
from .constants import (DHCHAP_DHGROUP,
                        DHCHAP_HASH,
                        NAMESPACE_DEVICE_TYPE,
                        NVMET_KERNEL_CONFIG_DIR,
                        NVMET_NODE_A_ANA_GRPID,
                        NVMET_NODE_A_MAX_CONTROLLER_ID,
                        NVMET_NODE_B_ANA_GRPID,
                        NVMET_NODE_B_MIN_CONTROLLER_ID,
                        PORT_ADDR_FAMILY,
                        PORT_TRTYPE)

ANA_OPTIMIZED_STATE = 'optimized'
ANA_INACCESSIBLE_STATE = 'inaccessible'
ANA_PORT_INDEX_OFFSET = 5000


class NvmetConfig:

    directory = None  # Directory below which the entities will be created
    query = None  # Query in the render_ctx that contains the entities
    query_key = None  # Field from the query used to name the directory entry

    def post_create(self, path: pathlib.Path, render_ctx: dict):
        pass

    def post_update(self, path: pathlib.Path, render_ctx: dict):
        pass

    def pre_delete(self, path: pathlib.Path, render_ctx: dict):
        pass

    def config_dict(self, render_ctx):
        return {str(entry[self.query_key]): entry for entry in render_ctx[self.query]}

    @contextmanager
    def render(self, render_ctx: dict):
        parent_dir = pathlib.Path(NVMET_KERNEL_CONFIG_DIR, self.directory)
        config = self.config_dict(render_ctx)
        config_keys = set(config.keys())
        live_keys = set(os.listdir(parent_dir))
        add_keys = config_keys - live_keys
        remove_keys = live_keys - config_keys
        update_keys = config_keys - remove_keys - add_keys
        # First make any required new directories.  Will call set_attrs
        # later to give the kernel time to prepare things
        for key in add_keys:
            pathlib.Path(parent_dir, key).mkdir()

        for key in update_keys:
            path = pathlib.Path(parent_dir, key)
            self.update_attrs(path, config[key], render_ctx)
            self.post_update(path, render_ctx)

        # Now ensure the newly created directories have the correct attributes
        retries = 10
        for key in add_keys:
            path = pathlib.Path(parent_dir, key)
            retries = self.set_attrs(path, config[key], retries, render_ctx)
            self.post_create(path, render_ctx)

        yield

        for key in remove_keys:
            path = pathlib.Path(NVMET_KERNEL_CONFIG_DIR, self.directory, key)
            self.pre_delete(path, render_ctx)
            path.rmdir()

    def set_mapped_attrs(self, path: pathlib.Path, attrs: dict, retries: int, render_ctx: dict):
        for k, v in attrs.items():
            p = pathlib.Path(path, k)
            while not p.exists() and retries > 0:
                time.sleep(1)
                retries -= 1
            p.write_text(f'{v}\n')
        return retries

    def set_attrs(self, path: pathlib.Path, attrs: dict, retries: int, render_ctx: dict):
        new_attrs = self.map_attrs(attrs, render_ctx)
        return self.set_mapped_attrs(path, new_attrs, retries, render_ctx)

    def values_match(self, oldval, newval):
        if oldval == newval:
            return True
        # Include the special case where we treat '\0' and '' the same
        if oldval == '' and newval == '\0':
            return True
        # Also try converting to string
        if oldval == str(newval):
            return True
        return False

    def update_attrs(self, path: pathlib.Path, attrs: dict, render_ctx: dict):
        new_attrs = self.map_attrs(attrs, render_ctx)
        for k, v in new_attrs.items():
            p = pathlib.Path(path, k)
            curval = p.read_text().strip()
            if not self.values_match(curval, v):
                p.write_text(f'{v}\n')


class NvmetHostConfig(NvmetConfig):
    directory = 'hosts'
    query = 'nvmet.host.query'
    query_key = 'hostnqn'

    def map_attrs(self, attrs: dict, render_ctx: dict):
        result = {}
        for k, v in attrs.items():
            if k in ('dhchap_key', 'dhchap_ctrl_key'):
                result[k] = '\0' if v is None else v
            elif k == 'dhchap_dhgroup':
                result[k] = DHCHAP_DHGROUP.by_api(v).sysfs
            elif k == 'dhchap_hash':
                result[k] = DHCHAP_HASH.by_api(v).sysfs
        return result


class NvmetPortConfig(NvmetConfig):
    directory = 'ports'
    query = 'nvmet.port.query'
    query_key = 'index'

    def config_dict(self, render_ctx):
        # For ports we may want to inject or remove ports wrt the ANA
        # settings.  ANA ports will be offset by ANA_PORT_INDEX_OFFSET (5000).
        config = {}
        non_ana_port_ids = render_ctx['nvmet.port.usage']['non_ana_port_ids']
        ana_port_ids = render_ctx['nvmet.port.usage']['ana_port_ids']
        for entry in render_ctx[self.query]:
            port_id = entry['id']
            if port_id in non_ana_port_ids:
                config[str(entry[self.query_key])] = entry
            if port_id in ana_port_ids:
                new_index = ANA_PORT_INDEX_OFFSET + entry[self.query_key]
                config[str(new_index)] = entry | {'index': new_index}
        return config

    def map_attrs(self, attrs: dict, render_ctx: dict):
        result = {}
        for k, v in attrs.items():
            match k:
                case 'addr_trtype':
                    result[k] = PORT_TRTYPE.by_api(v).sysfs
                case 'addr_adrfam':
                    result[k] = PORT_ADDR_FAMILY.by_api(v).sysfs
                case 'addr_traddr':
                    result[k] = v
                    if attrs.get('index', 0) > ANA_PORT_INDEX_OFFSET:
                        prefix = attrs['addr_trtype'].lower()
                        choices = render_ctx[f'{prefix}.nvmet.port.transport_address_choices']
                        pair = choices[v].split('/')
                        match render_ctx['failover.node']:
                            case 'A':
                                result[k] = pair[0]
                            case 'B':
                                result[k] = pair[1]
                case 'addr_trsvcid':
                    result[k] = v
                case 'inline_data_size':
                    if v is not None:
                        result['param_inline_data_size'] = str(v)
                case 'max_queue_size':
                    if v is not None:
                        result['param_max_queue_size'] = str(v)
                case 'pi_enable':
                    result['param_pi_enable'] = '0' if v in (None, False) else '1'

        return result

    def port_ana_path(self, path: pathlib.Path, render_ctx: dict):
        match render_ctx['failover.node']:
            case 'A':
                return pathlib.Path(path, 'ana_groups', str(NVMET_NODE_A_ANA_GRPID))
            case 'B':
                return pathlib.Path(path, 'ana_groups', str(NVMET_NODE_B_ANA_GRPID))
            case _:
                return None

    def ensure_ana_state(self, path: pathlib.Path, render_ctx: dict):
        if not render_ctx['failover.licensed']:
            return
        ana_path = self.port_ana_path(path, render_ctx)
        if render_ctx['nvmet.global.ana_active']:
            ana_path.mkdir(exist_ok=True)
            ana_state_path = pathlib.Path(ana_path, 'ana_state')
            cur_state = ana_state_path.read_text().strip()
            new_state = ANA_OPTIMIZED_STATE if render_ctx['failover.status'] == 'MASTER' else ANA_INACCESSIBLE_STATE
            if cur_state != new_state:
                ana_state_path.write_text(f'{new_state}\n')
        else:
            if ana_path.is_dir():
                ana_path.rmdir()

    def post_create(self, path: pathlib.Path, render_ctx: dict):
        self.ensure_ana_state(path, render_ctx)

    def post_update(self, path: pathlib.Path, render_ctx: dict):
        self.ensure_ana_state(path, render_ctx)

    def pre_delete(self, path: pathlib.Path, render_ctx: dict):
        if not render_ctx['failover.licensed']:
            return
        if ana_path := self.port_ana_path(path, render_ctx):
            if ana_path.is_dir():
                ana_path.rmdir()


class NvmetPortReferralConfig(NvmetConfig):
    directory = 'ports'
    query = 'nvmet.port.usage'
    query_key = 'non_ana_referrals'

    ITEMS = ('addr_trtype', 'addr_adrfam', 'addr_traddr', 'addr_trsvcid')

    def handle_port(self, index):
        return index < ANA_PORT_INDEX_OFFSET

    def index(self, index):
        return index

    def map_port_to_referral_attrs(self, attrs: dict, render_ctx: dict, remote: bool):
        return {
            'addr_trtype': PORT_TRTYPE.by_api(attrs['addr_trtype']).sysfs,
            'addr_adrfam': PORT_ADDR_FAMILY.by_api(attrs['addr_adrfam']).sysfs,
            'addr_traddr': attrs['addr_traddr'],
            'addr_trsvcid': str(attrs['addr_trsvcid']),
        }

    def read(self, parent: pathlib.Path):
        result = {}
        for item in self.ITEMS:
            result[item] = pathlib.Path(parent, item).read_text().strip()
        return result

    @contextmanager
    def modify(self, parent: pathlib.Path):
        enable_path = pathlib.Path(parent, 'enable')
        enable_path.write_text("0\n")
        try:
            yield
        finally:
            enable_path.write_text("1\n")

    def ports_by_index(self, render_ctx):
        return {self.index(port['index']): port for port in render_ctx['nvmet.port.query']}

    def update_referral(self, refdir, attrs):
        existing = self.read(refdir)
        if attrs != existing:
            with self.modify(refdir):
                for item in self.ITEMS:
                    if attrs[item] == existing[item]:
                        continue
                    pathlib.Path(refdir, item).write_text(f'{attrs[item]}\n')

    @contextmanager
    def render(self, render_ctx: dict):
        to_remove = []
        referral_ids = render_ctx[self.query][self.query_key]
        port_id_to_index = {port['id']: self.index(port['index']) for port in render_ctx['nvmet.port.query']}
        ports_by_index = self.ports_by_index(render_ctx)
        referrals = defaultdict(set)
        for src_id, dst_id in referral_ids:
            referrals[port_id_to_index[src_id]].add(port_id_to_index[dst_id])

        for portpath in pathlib.Path(NVMET_KERNEL_CONFIG_DIR, 'ports').iterdir():
            try:
                parent_index = int(portpath.name)
            except ValueError:
                continue

            # Are we the right *class* of port? (ANA vs non-ANA)
            if not self.handle_port(parent_index):
                continue

            referrals_path = pathlib.Path(portpath, 'referrals')
            # First check if there are any ports whose referrals are to be ENTIRELY removed
            if parent_index in referrals:
                # We're supposed to have some referrals.  Check for additions,
                # updates, removals.
                config_keys = {str(index) for index in referrals[parent_index]}
                live_keys = {ref.name for ref in referrals_path.iterdir() if ref.name.isnumeric}
                add_keys = config_keys - live_keys
                remove_keys = live_keys - config_keys
                update_keys = config_keys - remove_keys - add_keys

                to_remove.extend(pathlib.Path(referrals_path, key) for key in remove_keys)

                for key in add_keys:
                    pathlib.Path(referrals_path, key).mkdir()

                for key in update_keys:
                    index = int(key)
                    port = ports_by_index[index]
                    attrs = self.map_port_to_referral_attrs(port, render_ctx, parent_index == index)
                    self.update_referral(pathlib.Path(referrals_path, key), attrs)

                # Now ensure the newly created directories have the correct attributes
                retries = 10
                for key in add_keys:
                    index = int(key)
                    port = ports_by_index[index]
                    attrs = self.map_port_to_referral_attrs(port, render_ctx, parent_index == index)
                    attrs['enable'] = '1'
                    path = pathlib.Path(referrals_path, key)
                    retries = self.set_mapped_attrs(path, attrs, retries, render_ctx)
            else:
                to_remove.extend(referrals_path.iterdir())

        yield

        for path in to_remove:
            path.rmdir()


class NvmetPortAnaReferralConfig(NvmetPortReferralConfig):
    directory = 'ports'
    query = 'nvmet.port.usage'
    query_key = 'ana_referrals'

    def handle_port(self, index):
        return index >= ANA_PORT_INDEX_OFFSET

    def index(self, index):
        if index < ANA_PORT_INDEX_OFFSET:
            return index + ANA_PORT_INDEX_OFFSET
        else:
            return index

    def ports_by_index(self, render_ctx):
        # We want to update the index to the ANA specific one.
        # This will then be used by the map_port_to_referral_attrs in
        # this class to work out the address to be used.
        result = {}
        for port in render_ctx['nvmet.port.query']:
            new_index = self.index(port['index'])
            if new_index != port['index']:
                result[new_index] = port.copy() | {'index': new_index}
            else:
                result[new_index] = port
        return result

    def map_port_to_referral_attrs(self, attrs: dict, render_ctx: dict, remote: bool):
        data = super().map_port_to_referral_attrs(attrs, render_ctx, remote)
        # This is an ANA port, update the addr_traddr
        # We could be pointing at other ports on the same node, or on the
        # other node - specified by remote parameter
        if attrs.get('index', 0) > ANA_PORT_INDEX_OFFSET:
            curval = attrs['addr_traddr']
            prefix = attrs['addr_trtype'].lower()
            choices = render_ctx[f'{prefix}.nvmet.port.transport_address_choices']
            pair = choices[curval].split('/')
            match render_ctx['failover.node']:
                case 'A':
                    if remote:
                        newval = pair[1]
                    else:
                        newval = pair[0]
                case 'B':
                    if remote:
                        newval = pair[0]
                    else:
                        newval = pair[1]
            data['addr_traddr'] = newval
        return data


class NvmetSubsysConfig(NvmetConfig):
    directory = 'subsystems'
    query = 'nvmet.subsys.query'
    query_key = 'subnqn'

    def pre_delete(self, path: pathlib.Path, render_ctx: dict):
        # If we are force deleting a subsystem, then namespaces
        # will have been deleted from the config, but not yet
        # propagated live.  So, delete the namespaces here.
        for ns in pathlib.Path(path / 'namespaces').iterdir():
            ns.rmdir()

    def map_attrs(self, attrs: dict, render_ctx: dict):
        result = {}
        for k, v in attrs.items():
            match k:
                case 'serial':
                    result['attr_serial'] = v
                case 'allow_any_host':
                    result['attr_allow_any_host'] = '1' if v else '0'
                case 'pi_enable':
                    result['attr_pi_enable'] = '0' if v in (None, False) else '1'
                case 'qid_max' | 'ieee_oui':
                    if v:
                        result[f'attr_{k}'] = v
        # Perhaps inject some values
        match render_ctx['failover.node']:
            case 'A':
                result['attr_cntlid_max'] = NVMET_NODE_A_MAX_CONTROLLER_ID
            case 'B':
                result['attr_cntlid_min'] = NVMET_NODE_B_MIN_CONTROLLER_ID

        result['attr_model'] = render_ctx['nvmet.subsys.model']
        result['attr_firmware'] = render_ctx['nvmet.subsys.firmware']
        return result


class NvmetNamespaceConfig(NvmetConfig):
    directory = 'namespaces'
    query = 'nvmet.namespace.query'
    query_key = 'nsid'

    @contextmanager
    def render(self, render_ctx: dict):

        # First pre-process the data in the query
        subsys_to_subnqn = {}
        subsys_to_ns = defaultdict(dict)
        for entry in render_ctx[self.query]:
            subsys = entry['subsys']
            subsys_id = subsys['id']
            subsys_to_subnqn[subsys_id] = subsys['subnqn']
            subsys_to_ns[subsys_id][str(entry['nsid'])] = entry

        # We could have additional subsystems that no longer
        # have any namespaces attached.  Need to find them so that
        # we cleanup deleted namespaces.
        for subsys in render_ctx['nvmet.subsys.query']:
            subsys_id = subsys['id']
            if subsys_id not in subsys_to_ns:
                subsys_to_subnqn[subsys_id] = subsys['subnqn']
                subsys_to_ns[subsys_id] = {}

        remove_dirs = []
        for subsys_id, namespaces in subsys_to_ns.items():
            parent_dir = pathlib.Path(NVMET_KERNEL_CONFIG_DIR,
                                      'subsystems',
                                      subsys_to_subnqn[subsys_id],
                                      self.directory)

            config_keys = set(namespaces.keys())
            live_keys = set(os.listdir(parent_dir))
            add_keys = config_keys - live_keys
            remove_keys = live_keys - config_keys
            update_keys = config_keys - remove_keys - add_keys
            # First make any required new directories.  Will call set_attrs
            # later to give the kernel time to prepare things
            for key in add_keys:
                pathlib.Path(parent_dir, key).mkdir()

            for key in update_keys:
                self.update_attrs(pathlib.Path(parent_dir, key), namespaces[key], render_ctx)

            # Now ensure the newly created directories have the correct attributes
            retries = 10
            for key in add_keys:
                retries = self.set_attrs(pathlib.Path(parent_dir, key), namespaces[key], retries, render_ctx)

            for key in remove_keys:
                remove_dirs.append(pathlib.Path(parent_dir, key))

        yield

        for d in remove_dirs:
            d.rmdir()

    def map_attrs(self, attrs: dict, render_ctx: dict):
        result = {}
        for k in ('device_uuid', 'device_nguid'):
            result[k] = attrs[k]

        device_path = attrs.get('device_path')
        if device_path and not attrs['locked']:
            if dp := _map_device_path(attrs['device_type'], device_path):
                result['device_path'] = dp

        result['buffered_io'] = NAMESPACE_DEVICE_TYPE.by_api(attrs['device_type']).sysfs

        result['resv_enable'] = 1
        result['ana_grpid'] = 1

        do_ana = False
        # Is ANA active for this namespace (subsystem)
        if render_ctx['nvmet.global.ana_active']:
            # Maybe ANA applies to this namespace
            if isinstance(subsys_ana := attrs['subsys']['ana'], bool):
                do_ana = subsys_ana
            else:
                do_ana = bool(render_ctx['nvmet.global.ana_enabled'])

        if do_ana:
            match render_ctx['failover.node']:
                case 'A':
                    result['ana_grpid'] = NVMET_NODE_A_ANA_GRPID
                case 'B':
                    result['ana_grpid'] = NVMET_NODE_B_ANA_GRPID

        match render_ctx['failover.status']:
            case 'SINGLE' | 'MASTER':
                result['enable'] = '1' if attrs['enabled'] and not attrs['locked'] else '0'
            case 'BACKUP':
                result['enable'] = '0'

        return result


class NvmetLinkConfig:
    query = None
    src_parentdir = None
    src_subdir = None
    src_query_keys = []
    dst_dir = None
    dst_query_keys = []

    def src_name_prefix(self, render_ctx: dict):
        return ''

    def dst_name_prefix(self, render_ctx: dict):
        return ''

    def create_links(self, entry: dict, render_ctx: dict):
        return True

    @contextmanager
    def render(self, render_ctx: dict):
        # First we will see if any link sources need to be entirely removed
        src_to_dst = defaultdict(set)
        for entry in render_ctx[self.query]:
            if self.create_links(entry, render_ctx):
                if _src_dir_name := self.src_dir_name(entry, render_ctx):
                    src_to_dst[_src_dir_name].add(self.dst_name(entry))
        rootdir = pathlib.Path(NVMET_KERNEL_CONFIG_DIR, self.src_parentdir)
        dstdir = pathlib.Path(NVMET_KERNEL_CONFIG_DIR, self.dst_dir)
        to_unlink = []
        for path in rootdir.glob(f'*/{self.src_subdir}/*'):
            if path.is_symlink():
                name = path.name
                parent = path.parent.parent.name
                if parent not in src_to_dst:
                    # This parent is not supposed to have ANY links.  Remove it
                    to_unlink.append(path)
                else:
                    if name in src_to_dst[parent]:
                        # It exists & should exist.  Remove it so that
                        # when we have finished iterating anything remaining
                        # in src_to_dst needs to be created
                        src_to_dst[parent].remove(name)
                    else:
                        # It exists but should not.  Remove the link
                        to_unlink.append(path)
        # OK, now create anything required that was missing
        for k, v in src_to_dst.items():
            if not v:
                continue
            srcdir = pathlib.Path(rootdir, k, self.src_subdir)
            for entry_name in v:
                new_link = pathlib.Path(srcdir, entry_name)
                new_link.symlink_to(pathlib.Path(dstdir, entry_name))

        yield

        # Remove any links no longer required
        for link in to_unlink:
            link.unlink()


class NvmetHostSubsysConfig(NvmetLinkConfig):
    query = 'nvmet.host_subsys.query'
    src_parentdir = 'subsystems'
    src_subdir = 'allowed_hosts'
    src_query_keys = ['subsys', 'subnqn']
    dst_dir = 'hosts'
    dst_query_keys = ['host', 'hostnqn']

    def src_dir_name(self, entry, render_ctx: dict):
        return f'{entry[self.src_query_keys[0]][self.src_query_keys[1]]}'

    def dst_name(self, entry):
        return f'{entry[self.dst_query_keys[0]][self.dst_query_keys[1]]}'


class NvmetPortSubsysConfig(NvmetLinkConfig):
    query = 'nvmet.port_subsys.query'
    src_parentdir = 'ports'
    src_subdir = 'subsystems'
    src_query_keys = ['port', 'index']
    dst_dir = 'subsystems'
    dst_query_keys = ['subsys', 'subnqn']

    def src_dir_name(self, entry, render_ctx: dict):
        # Because we have elected to support overriding the global ANA
        # setting for individual subsystems this has two knock-on effects
        # 1. Additional ANA-specific port indexes are in injected
        # 2. Particular subsystems will link to either the ANA or non-ANA
        #    port index.
        # However, if we're on the standby node we never want to setup
        # a link to the VIP port.
        raw_index = entry[self.src_query_keys[0]][self.src_query_keys[1]]
        # Now check whether ANA is playing a part.
        match entry['subsys']['ana']:
            case True:
                index = raw_index + ANA_PORT_INDEX_OFFSET
            case False:
                index = raw_index
            case _:
                if render_ctx['nvmet.global.ana_enabled']:
                    index = raw_index + ANA_PORT_INDEX_OFFSET
                else:
                    index = raw_index

        if index < ANA_PORT_INDEX_OFFSET and render_ctx['failover.status'] == 'BACKUP':
            return None

        return str(index)

    def dst_name(self, entry):
        return f'{entry[self.dst_query_keys[0]][self.dst_query_keys[1]]}'

    def create_links(self, entry: dict, render_ctx: dict):
        # There are two reasons why we might NOT want to create a link
        # 1. The port is not enabled
        # 2. The port is RDMA, but the global RDMA setting is off
        if not entry['port']['enabled']:
            return False
        if entry['port']['addr_trtype'] == PORT_TRTYPE.RDMA.api and not render_ctx['nvmet.global.rdma_enabled']:
            return False
        return True


def write_config(config):
    if not pathlib.Path(NVMET_KERNEL_CONFIG_DIR).exists():
        return

    # Render operations are context managers that do
    # 1. Create-style operations
    # 2. yield
    # 3. Delete-style operations
    #
    # Therefore we can nest them to enfore the necessary
    # order of operations.
    with (
        NvmetSubsysConfig().render(config),
        NvmetHostConfig().render(config),
        NvmetPortConfig().render(config),
        NvmetPortReferralConfig().render(config),
        NvmetPortAnaReferralConfig().render(config),
        NvmetHostSubsysConfig().render(config),
        NvmetPortSubsysConfig().render(config),
        NvmetNamespaceConfig().render(config),
    ):
        pass


def _map_device_path(device_type, device_path):
    match device_type:
        case 'FILE':
            if device_path.startswith('/mnt/'):
                return device_path
        case 'ZVOL':
            if device_path.startswith('zvol/'):
                return zvol_name_to_path(device_path[5:])


def _set_namespace_field(subnqn, nsnum, field, value):
    try:
        pathlib.Path(NVMET_KERNEL_CONFIG_DIR,
                     'subsystems',
                     subnqn,
                     'namespaces',
                     str(nsnum),
                     field).write_text(f'{value}\n')
    except FileNotFoundError:
        pass


def _set_namespace_enable(subnqn, nsnum, value):
    _set_namespace_field(subnqn, nsnum, 'enable', value)


def lock_namespace(data):
    _set_namespace_enable(data['subsys']['subnqn'], data['nsid'], 0)


def unlock_namespace(data):
    _set_namespace_field(data['subsys']['subnqn'],
                         data['nsid'],
                         'device_path',
                         _map_device_path(data['device_type'], data['device_path']))
    _set_namespace_enable(data['subsys']['subnqn'], data['nsid'], 1)


def resize_namespace(data):
    _set_namespace_field(data['subsys']['subnqn'],
                         data['nsid'],
                         'revalidate_size',
                         1)


def clear_config():
    config_root = pathlib.Path(NVMET_KERNEL_CONFIG_DIR)
    if not config_root.exists():
        return

    for port in pathlib.Path(config_root, 'ports').iterdir():
        for subsys in pathlib.Path(port, 'subsystems').iterdir():
            subsys.unlink()
        for referral in pathlib.Path(port, 'referrals').iterdir():
            referral.rmdir()
        for ana in pathlib.Path(port, 'ana_groups').iterdir():
            if ana.name != '1':
                ana.rmdir()
        port.rmdir()

    for subsys in pathlib.Path(config_root, 'subsystems').iterdir():
        for host in pathlib.Path(subsys, 'allowed_hosts').iterdir():
            host.unlink()
        for ns in pathlib.Path(subsys, 'namespaces').iterdir():
            ns.rmdir()
        subsys.rmdir()

    for host in pathlib.Path(config_root, 'hosts').iterdir():
        host.rmdir()


def nvmet_kernel_module_loaded():
    return pathlib.Path(NVMET_KERNEL_CONFIG_DIR).is_dir()


def load_modules(modules):
    if modules:
        command = ['modprobe', '-a'] + modules
        subprocess.run(command)


def unload_module(mod):
    command = ['rmmod', mod]
    subprocess.run(command, capture_output=True)
