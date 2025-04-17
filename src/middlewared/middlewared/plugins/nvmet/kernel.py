import abc
import os
import pathlib
import subprocess
import time
from collections import defaultdict
from contextlib import contextmanager

from middlewared.plugins.zfs_.utils import zvol_name_to_path
from .constants import (DHCHAP_DHGROUP, DHCHAP_HASH, NAMESPACE_DEVICE_TYPE, NVMET_KERNEL_CONFIG_DIR,
                        NVMET_NODE_A_ANA_GRPID, NVMET_NODE_B_ANA_GRPID, PORT_ADDR_FAMILY, PORT_TRTYPE)

ANA_OPTIMIZED_STATE = 'optimized'
ANA_INACCESSIBLE_STATE = 'inaccessible'
ANA_PORT_INDEX_OFFSET = 5000


class NvmetConfig(abc.ABC):

    directory = None  # Directory below which the entities will be created
    query = None  # Query in the render_ctx that contains the entities
    query_key = None  # Field from the query used to name the directory entry

    @classmethod
    def post_create(cls, path: pathlib.Path, render_ctx: dict):
        pass

    @classmethod
    def post_update(cls, path: pathlib.Path, render_ctx: dict):
        pass

    @classmethod
    def pre_delete(cls, path: pathlib.Path, render_ctx: dict):
        pass

    @classmethod
    def config_dict(cls, render_ctx):
        return {str(entry[cls.query_key]): entry for entry in render_ctx[cls.query]}

    @classmethod
    @contextmanager
    def render(cls, render_ctx: dict):
        parent_dir = pathlib.Path(NVMET_KERNEL_CONFIG_DIR, cls.directory)
        config = cls.config_dict(render_ctx)
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
            cls.update_attrs(path, config[key], render_ctx)
            cls.post_update(path, render_ctx)

        # Now ensure the newly created directories have the correct attributes
        retries = 10
        for key in add_keys:
            path = pathlib.Path(parent_dir, key)
            retries = cls.set_attrs(path, config[key], retries, render_ctx)
            cls.post_create(path, render_ctx)

        yield

        for key in remove_keys:
            path = pathlib.Path(NVMET_KERNEL_CONFIG_DIR, cls.directory, key)
            cls.pre_delete(path, render_ctx)
            path.rmdir()

    @classmethod
    def set_mapped_attrs(cls, path: pathlib.Path, attrs: dict, retries: int, render_ctx: dict):
        for k, v in attrs.items():
            p = pathlib.Path(path, k)
            # DEBUG print(f"Want to write {v} to {p}")
            while not p.exists() and retries > 0:
                time.sleep(1)
                retries -= 1
            p.write_text(f'{v}\n')
        return retries

    @classmethod
    def set_attrs(cls, path: pathlib.Path, attrs: dict, retries: int, render_ctx: dict):
        new_attrs = cls.map_attrs(attrs, render_ctx)
        return cls.set_mapped_attrs(path, new_attrs, retries, render_ctx)

    @staticmethod
    def values_match(oldval, newval):
        if oldval == newval:
            return True
        # Include the special case where we treat '\0' and '' the same
        if oldval == '' and newval == '\0':
            return True
        # Also try converting to string
        if oldval == str(newval):
            return True
        return False

    @classmethod
    def update_attrs(cls, path: pathlib.Path, attrs: dict, render_ctx: dict):
        new_attrs = cls.map_attrs(attrs, render_ctx)
        for k, v in new_attrs.items():
            p = pathlib.Path(path, k)
            curval = p.read_text().strip()
            if not cls.values_match(curval, v):
                # print(f"Writing {k} value *{v}* to {p} [current value: *{curval}*]")
                p.write_text(f'{v}\n')


class NvmetHostConfig(NvmetConfig):
    directory = 'hosts'
    query = 'nvmet.host.query'
    query_key = 'hostnqn'

    @classmethod
    def map_attrs(cls, attrs: dict, render_ctx: dict):
        result = {}
        for k, v in attrs.items():
            if k in ['dhchap_key', 'dhchap_ctrl_key']:
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

    @classmethod
    def config_dict(cls, render_ctx):
        # For ports we may want to inject or remove ports wrt the ANA
        # settings.  ANA ports will be offset by ANA_PORT_INDEX_OFFSET (5000).
        config = {}
        non_ana_port_ids = render_ctx['nvmet.port.usage']['non_ana_port_ids']
        ana_port_ids = render_ctx['nvmet.port.usage']['ana_port_ids']
        for entry in render_ctx[cls.query]:
            port_id = entry['id']
            if port_id in non_ana_port_ids:
                config[str(entry[cls.query_key])] = entry
            if port_id in ana_port_ids:
                new_index = ANA_PORT_INDEX_OFFSET + entry[cls.query_key]
                config[str(new_index)] = entry | {'index': new_index}
        return config

    @classmethod
    def map_attrs(cls, attrs: dict, render_ctx: dict):
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
                    result['param_pi_enable'] = '0' if v in [None, False] else '1'

        return result

    @classmethod
    def port_ana_path(cls, path: pathlib.Path, render_ctx: dict):
        match render_ctx['failover.node']:
            case 'A':
                return pathlib.Path(path, 'ana_groups', str(NVMET_NODE_A_ANA_GRPID))
            case 'B':
                return pathlib.Path(path, 'ana_groups', str(NVMET_NODE_B_ANA_GRPID))
            case _:
                return None

    @classmethod
    def ensure_ana_state(cls, path: pathlib.Path, render_ctx: dict):
        if not render_ctx['failover.licensed']:
            return
        ana_path = cls.port_ana_path(path, render_ctx)
        if render_ctx['nvmet.global.ana_active']:
            if not ana_path.is_dir():
                ana_path.mkdir()
            ana_state_path = pathlib.Path(ana_path, 'ana_state')
            cur_state = ana_state_path.read_text().strip()
            new_state = ANA_OPTIMIZED_STATE if render_ctx['failover.status'] == 'MASTER' else ANA_INACCESSIBLE_STATE
            if cur_state != new_state:
                ana_state_path.write_text(f'{new_state}\n')
        else:
            if ana_path.is_dir():
                ana_path.rmdir()

    @classmethod
    def post_create(cls, path: pathlib.Path, render_ctx: dict):
        cls.ensure_ana_state(path, render_ctx)

    @classmethod
    def post_update(cls, path: pathlib.Path, render_ctx: dict):
        cls.ensure_ana_state(path, render_ctx)

    @classmethod
    def pre_delete(cls, path: pathlib.Path, render_ctx: dict):
        if not render_ctx['failover.licensed']:
            return
        if ana_path := cls.port_ana_path(path, render_ctx):
            if ana_path.is_dir():
                ana_path.rmdir()


class NvmetPortReferralConfig(NvmetConfig):
    directory = 'ports'
    query = 'nvmet.port.usage'
    query_key = 'non_ana_referrals'

    ITEMS = ['addr_trtype', 'addr_adrfam', 'addr_traddr', 'addr_trsvcid']

    @classmethod
    def handle_port(cls, index):
        return index < ANA_PORT_INDEX_OFFSET

    @classmethod
    def index(cls, index):
        return index

    @classmethod
    def map_port_to_referral_attrs(cls, attrs: dict, render_ctx: dict, remote: bool):
        return {
            'addr_trtype': PORT_TRTYPE.by_api(attrs['addr_trtype']).sysfs,
            'addr_adrfam': PORT_ADDR_FAMILY.by_api(attrs['addr_adrfam']).sysfs,
            'addr_traddr': attrs['addr_traddr'],
            'addr_trsvcid': str(attrs['addr_trsvcid']),
        }

    @classmethod
    def read(cls, parent: pathlib.Path):
        result = {}
        for item in cls.ITEMS:
            result[item] = pathlib.Path(parent, item).read_text().strip()
        return result

    @classmethod
    @contextmanager
    def modify(cls, parent: pathlib.Path):
        enable_path = pathlib.Path(parent, 'enable')
        enable_path.write_text("0\n")
        try:
            yield
        finally:
            enable_path.write_text("1\n")

    @classmethod
    def ports_by_index(cls, render_ctx):
        return {cls.index(port['index']): port for port in render_ctx['nvmet.port.query']}

    @classmethod
    def update_referral(cls, refdir, attrs):
        existing = cls.read(refdir)
        if attrs != existing:
            with cls.modify(refdir):
                for item in cls.ITEMS:
                    if attrs[item] == existing[item]:
                        continue
                    pathlib.Path(refdir, item).write_text(f'{attrs[item]}\n')

    @classmethod
    @contextmanager
    def render(cls, render_ctx: dict):
        to_remove = []
        referral_ids = render_ctx[cls.query][cls.query_key]
        port_id_to_index = {port['id']: cls.index(port['index']) for port in render_ctx['nvmet.port.query']}
        ports_by_index = cls.ports_by_index(render_ctx)
        referrals = defaultdict(set)
        for src_id, dst_id in referral_ids:
            referrals[port_id_to_index[src_id]].add(port_id_to_index[dst_id])

        for portpath in pathlib.Path(NVMET_KERNEL_CONFIG_DIR, 'ports').iterdir():
            try:
                parent_index = int(portpath.name)
            except ValueError:
                continue

            # Are we the right *class* of port? (ANA vs non-ANA)
            if not cls.handle_port(parent_index):
                continue

            referrals_path = pathlib.Path(portpath, 'referrals')
            # First check if there are any ports whose referrals are to be ENTIRELY removed
            if parent_index not in referrals:
                for referral_path in referrals_path.iterdir():
                    to_remove.append(referral_path)
            else:
                # We're supposed to have some referrals.  Check for additions,
                # updates, removals.
                config_keys = {str(index) for index in referrals[parent_index]}
                live_keys = {ref.name for ref in referrals_path.iterdir() if ref.name.isnumeric}
                add_keys = config_keys - live_keys
                remove_keys = live_keys - config_keys
                update_keys = config_keys - remove_keys - add_keys

                for key in remove_keys:
                    to_remove.append(pathlib.Path(referrals_path, key))

                for key in add_keys:
                    pathlib.Path(referrals_path, key).mkdir()

                for key in update_keys:
                    index = int(key)
                    port = ports_by_index[index]
                    attrs = cls.map_port_to_referral_attrs(port, render_ctx, parent_index == index)
                    cls.update_referral(pathlib.Path(referrals_path, key), attrs)

                # Now ensure the newly created directories have the correct attributes
                retries = 10
                for key in add_keys:
                    index = int(key)
                    port = ports_by_index[index]
                    attrs = cls.map_port_to_referral_attrs(port, render_ctx, parent_index == index)
                    attrs['enable'] = '1'
                    path = pathlib.Path(referrals_path, key)
                    retries = cls.set_mapped_attrs(path, attrs, retries, render_ctx)

        yield

        for path in to_remove:
            path.rmdir()


class NvmetPortAnaReferralConfig(NvmetPortReferralConfig):
    directory = 'ports'
    query = 'nvmet.port.usage'
    query_key = 'ana_referrals'

    @classmethod
    def handle_port(cls, index):
        return index >= ANA_PORT_INDEX_OFFSET

    @classmethod
    def index(cls, index):
        if index < ANA_PORT_INDEX_OFFSET:
            return index + ANA_PORT_INDEX_OFFSET
        else:
            return index

    @classmethod
    def ports_by_index(cls, render_ctx):
        # We want to update the index to the ANA specific one.
        # This will then be used by the map_port_to_referral_attrs in
        # this class to work out the address to be used.
        result = {}
        for port in render_ctx['nvmet.port.query']:
            new_index = cls.index(port['index'])
            if new_index != port['index']:
                result[new_index] = port.copy() | {'index': new_index}
            else:
                result[new_index] = port
        return result

    @classmethod
    def map_port_to_referral_attrs(cls, attrs: dict, render_ctx: dict, remote: bool):
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

    @classmethod
    def pre_delete(cls, path: pathlib.Path, render_ctx: dict):
        # If we are force deleting a subsystem, then namespaces
        # will have been deleted from the config, but not yet
        # propagated live.  So, delete the namespaces here.
        for ns in pathlib.Path(path / 'namespaces').iterdir():
            ns.rmdir()

    @classmethod
    def map_attrs(cls, attrs: dict, render_ctx: dict):
        result = {}
        for k, v in attrs.items():
            match k:
                case 'serial':
                    result['attr_serial'] = v
                case 'allow_any_host':
                    result['attr_allow_any_host'] = '1' if v else '0'
                case 'pi_enable':
                    result['attr_pi_enable'] = '0' if v in [None, False] else '1'
                case 'qid_max' | 'ieee_oui':
                    if v:
                        result[f'attr_{k}'] = v
        # Perhaps inject some values
        match render_ctx['failover.node']:
            case 'A':
                result['attr_cntlid_max'] = 31999
            case 'B':
                result['attr_cntlid_min'] = 32000

        if render_ctx['system.vendor.name']:
            result['attr_model'] = render_ctx['system.info'].get('system_product', render_ctx['system.vendor.name'])
        else:
            name = render_ctx['system.info'].get('system_product', 'TrueNAS')
            if name.lower().startswith('truenas'):
                result['attr_model'] = name
            else:
                result['attr_model'] = f'TrueNAS {name}'

        result['attr_firmware'] = render_ctx['system.info'].get('version', 'Unknown')[:8]
        return result


class NvmetNamespaceConfig(NvmetConfig):
    directory = 'namespaces'
    query = 'nvmet.namespace.query'
    query_key = 'nsid'

    @classmethod
    @contextmanager
    def render(cls, render_ctx: dict):

        # First pre-process the data in the query
        subsys_to_subnqn = {}
        subsys_to_ns = defaultdict(dict)
        for entry in render_ctx[cls.query]:
            subsys = entry['subsys']
            subsys_id = subsys['id']
            subsys_to_subnqn[subsys_id] = subsys['nvmet_subsys_subnqn']
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
                                      cls.directory)

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
                cls.update_attrs(pathlib.Path(parent_dir, key), namespaces[key], render_ctx)

            # Now ensure the newly created directories have the correct attributes
            retries = 10
            for key in add_keys:
                retries = cls.set_attrs(pathlib.Path(parent_dir, key), namespaces[key], retries, render_ctx)

            for key in remove_keys:
                remove_dirs.append(pathlib.Path(parent_dir, key))

        yield

        for d in remove_dirs:
            d.rmdir()

    @classmethod
    def map_attrs(cls, attrs: dict, render_ctx: dict):
        result = {}
        for k in ['device_uuid', 'device_nguid']:
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
            match attrs['subsys']['nvmet_subsys_ana']:
                case True:
                    do_ana = True
                case False:
                    do_ana = False
                case _:
                    if render_ctx['nvmet.global.ana_enabled']:
                        do_ana = True
                    else:
                        do_ana = False

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


class NvmetLinkConfig(abc.ABC):
    query = None
    src_parentdir = None
    src_subdir = None
    src_query_keys = []
    dst_dir = None
    dst_query_keys = []

    @classmethod
    def src_name_prefix(cls, render_ctx: dict):
        return ''

    @classmethod
    def dst_name_prefix(cls, render_ctx: dict):
        return ''

    @classmethod
    def create_links(cls, entry: dict):
        return True

    @classmethod
    @contextmanager
    def render(cls, render_ctx: dict):
        # First we will see if any link sources need to be entirely removed
        src_to_dst = defaultdict(set)
        for entry in render_ctx[cls.query]:
            if cls.create_links(entry):
                if _src_dir_name := cls.src_dir_name(entry, render_ctx):
                    src_to_dst[_src_dir_name].add(cls.dst_name(entry))
        rootdir = pathlib.Path(NVMET_KERNEL_CONFIG_DIR, cls.src_parentdir)
        dstdir = pathlib.Path(NVMET_KERNEL_CONFIG_DIR, cls.dst_dir)
        to_unlink = []
        for path in rootdir.glob(f'*/{cls.src_subdir}/*'):
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
            srcdir = pathlib.Path(rootdir, k, cls.src_subdir)
            for entry_name in v:
                new_link = pathlib.Path(srcdir, entry_name)
                # DEBUG print("Making link", k, entry_name)
                new_link.symlink_to(pathlib.Path(dstdir, entry_name))

        yield

        # Remove any links no longer required
        for link in to_unlink:
            # DEBUG print("Removing link", path)
            link.unlink()


class NvmetHostSubsysConfig(NvmetLinkConfig):
    query = 'nvmet.host_subsys.query'
    src_parentdir = 'subsystems'
    src_subdir = 'allowed_hosts'
    src_query_keys = ['subsys', 'nvmet_subsys_subnqn']
    dst_dir = 'hosts'
    dst_query_keys = ['host', 'nvmet_host_hostnqn']

    @classmethod
    def src_dir_name(cls, entry, render_ctx: dict):
        return f'{entry[cls.src_query_keys[0]][cls.src_query_keys[1]]}'

    @classmethod
    def dst_name(cls, entry):
        return f'{entry[cls.dst_query_keys[0]][cls.dst_query_keys[1]]}'


class NvmetPortSubsysConfig(NvmetLinkConfig):
    query = 'nvmet.port_subsys.query'
    src_parentdir = 'ports'
    src_subdir = 'subsystems'
    src_query_keys = ['port', 'nvmet_port_index']
    dst_dir = 'subsystems'
    dst_query_keys = ['subsys', 'nvmet_subsys_subnqn']

    @classmethod
    def src_dir_name(cls, entry, render_ctx: dict):
        # Because we have elected to support overriding the global ANA
        # setting for individual subsystems this has two knock-on effects
        # 1. Additional ANA-specific port indexes are in injected
        # 2. Particular subsystems will link to either the ANA or non-ANA
        #    port index.
        # However, if we're on the standby node we never want to setup
        # a link to the VIP port.
        raw_index = entry[cls.src_query_keys[0]][cls.src_query_keys[1]]
        # Now check whether ANA is playing a part.
        match entry['subsys']['nvmet_subsys_ana']:
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

    @classmethod
    def dst_name(cls, entry):
        return f'{entry[cls.dst_query_keys[0]][cls.dst_query_keys[1]]}'

    @classmethod
    def create_links(cls, entry: dict):
        return entry['port']['nvmet_port_enabled']


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
    with NvmetSubsysConfig.render(config):
        with NvmetHostConfig.render(config):
            with NvmetPortConfig.render(config):
                with NvmetPortReferralConfig.render(config):
                    with NvmetPortAnaReferralConfig.render(config):
                        with NvmetHostSubsysConfig.render(config):
                            with NvmetPortSubsysConfig.render(config):
                                with NvmetNamespaceConfig.render(config):
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
    p = pathlib.Path(NVMET_KERNEL_CONFIG_DIR,
                     'subsystems',
                     subnqn,
                     'namespaces',
                     str(nsnum),
                     field)
    try:
        p.write_text(f'{value}\n')
    except FileNotFoundError:
        pass


def _set_namespace_enable(subnqn, nsnum, value):
    _set_namespace_field(subnqn, nsnum, 'enable', value)


def lock_namespace(data):
    _set_namespace_enable(data['subsys']['nvmet_subsys_subnqn'], data['nsid'], 0)


def unlock_namespace(data):
    _set_namespace_field(data['subsys']['nvmet_subsys_subnqn'],
                         data['nsid'],
                         'device_path',
                         _map_device_path(data['device_type'], data['device_path']))
    _set_namespace_enable(data['subsys']['nvmet_subsys_subnqn'], data['nsid'], 1)


def resize_namespace(data):
    _set_namespace_field(data['subsys']['nvmet_subsys_subnqn'],
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
