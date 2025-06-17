import pathlib

import middlewared.sqlalchemy as sa
from middlewared.api import api_method
from middlewared.api.current import (NVMetGlobalEntry,
                                     NVMetGlobalUpdateArgs,
                                     NVMetGlobalUpdateResult,
                                     NVMetGlobalSessionsItem)
from middlewared.plugins.rdma.constants import RDMAprotocols
from middlewared.service import SystemServiceService, ValidationErrors, filterable_api_method, private
from middlewared.utils import filter_list
from .constants import NVMET_SERVICE_NAME
from middlewared.utils.nvmet.kernel import clear_config, load_modules, nvmet_kernel_module_loaded, unload_module
from middlewared.utils.nvmet.spdk import make_client, nvmf_subsystem_get_qpairs
from .mixin import NVMetStandbyMixin
from .utils import uuid_nqn

NVMET_DEBUG_DIR = '/sys/kernel/debug/nvmet'
NVMF_SERVICE = 'nvmf'
AVX2_FLAG = 'avx2'


class NVMetGlobalModel(sa.Model):
    __tablename__ = 'services_nvmet_global'

    id = sa.Column(sa.Integer(), primary_key=True)
    nvmet_global_basenqn = sa.Column(sa.String(255), default=uuid_nqn)
    nvmet_global_kernel = sa.Column(sa.Boolean(), default=True)
    nvmet_global_ana = sa.Column(sa.Boolean(), default=False)
    nvmet_global_rdma = sa.Column(sa.Boolean(), default=False)
    nvmet_global_xport_referral = sa.Column(sa.Boolean(), default=True)


class NVMetGlobalService(SystemServiceService, NVMetStandbyMixin):

    class Config:
        namespace = 'nvmet.global'
        datastore = 'services.nvmet_global'
        datastore_prefix = 'nvmet_global_'
        service = NVMET_SERVICE_NAME
        cli_private = True
        role_prefix = 'SHARING_NVME_TARGET'
        entry = NVMetGlobalEntry

    @api_method(
        NVMetGlobalUpdateArgs,
        NVMetGlobalUpdateResult,
        audit='Update NVMe target global'
    )
    async def do_update(self, data):
        """
        Update NVMe target global config.
        """
        old = await self.config()

        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()
        await self.__validate(verrors, new, 'nvmet_global_update', old=old)
        verrors.check()

        async with self._handle_standby_service_state(old['ana'] != new['ana'] and await self.running()):
            await self._update_service(old, new)

        return await self.config()

    async def __ana_forbidden(self):
        return not await self.middleware.call('failover.licensed')

    async def __spdk_forbidden(self):
        # For now we'll disallow SPDK if any CPU is missing avx2
        return any(AVX2_FLAG not in flags for flags in (await self.middleware.call('system.cpu_flags')).values())

    async def __validate(self, verrors, data, schema_name, old=None):
        if data['rdma'] and old['rdma'] != data['rdma']:
            available_rdma_protocols = await self.middleware.call('rdma.capable_protocols')
            if RDMAprotocols.NVMET.value not in available_rdma_protocols:
                verrors.add(
                    f'{schema_name}.rdma',
                    'This platform cannot support NVMe-oF(RDMA) or is missing a RDMA capable NIC.'
                )
        if old['ana'] != data['ana']:
            if data['ana'] and await self.__ana_forbidden():
                verrors.add(
                    f'{schema_name}.ana',
                    'This platform does not support Asymmetric Namespace Access(ANA).'
                )
        if old['kernel'] != data['kernel']:
            if not data['kernel'] and await self.__spdk_forbidden():
                verrors.add(
                    f'{schema_name}.kernel',
                    'Cannot switch nvmet backend because CPU lacks required capabilities.'
                )
            elif await self.running():
                verrors.add(
                    f'{schema_name}.kernel',
                    'Cannot switch nvmet backend while the service is running.'
                )

    @private
    async def ana_enabled(self):
        """
        Returns whether NVMe target ANA is enabled or not.
        """
        if await self.__ana_forbidden():
            return False

        return (await self.middleware.call('nvmet.global.config'))['ana']

    @private
    async def ana_active(self):
        # Similar to ana_enabled, but also takes into account
        # the per-subsystem ANA setting.
        if await self.__ana_forbidden():
            return False

        if (await self.middleware.call('nvmet.global.config'))['ana']:
            return True

        if (await self.middleware.call('nvmet.port.usage'))['ana_port_ids']:
            return True

        return False

    @private
    async def rdma_enabled(self):
        """
        Returns whether RDMA is enabled or not.
        """
        if not await self.middleware.call('system.is_enterprise'):
            return False

        return (await self.middleware.call('nvmet.global.config'))['rdma']

    @filterable_api_method(item=NVMetGlobalSessionsItem, roles=['SHARING_NVME_TARGET_READ'])
    async def sessions(self, filters, options):
        sessions = []
        subsys_id = None
        for _filter in filters:
            if len(_filter) == 3 and _filter[0] == 'subsys_id' and _filter[1] == '=':
                subsys_id = _filter[2]
                break
        sessions = await self.middleware.call('nvmet.global.local_sessions', subsys_id)
        if await self.ana_enabled():
            sessions.extend(await self.middleware.call('failover.call_remote',
                                                       'nvmet.global.local_sessions',
                                                       [subsys_id]))

        return filter_list(sessions, filters, options)

    def __parse_session_dir(self, path: pathlib.Path, port_index_to_id: dict):
        """
        Parse the session directory, e.g.
        /sys/kernel/debug/nvmet/<SUBSYS_NQN>/ctrl<NUMBER>
        """
        # For example
        # /sys/kernel/debug/nvmet/nqn.2011-06.com.truenas:uuid:cef24057-8050-4fc7-ab87-773e19b32b0e:foo1/ctrl2
        # /sys/kernel/debug/nvmet/nqn.2011-06.com.truenas:uuid:cef24057-8050-4fc7-ab87-773e19b32b0e:foo1/ctrl2/host_traddr
        # /sys/kernel/debug/nvmet/nqn.2011-06.com.truenas:uuid:cef24057-8050-4fc7-ab87-773e19b32b0e:foo1/ctrl2/state
        # /sys/kernel/debug/nvmet/nqn.2011-06.com.truenas:uuid:cef24057-8050-4fc7-ab87-773e19b32b0e:foo1/ctrl2/kato
        # /sys/kernel/debug/nvmet/nqn.2011-06.com.truenas:uuid:cef24057-8050-4fc7-ab87-773e19b32b0e:foo1/ctrl2/hostnqn
        # /sys/kernel/debug/nvmet/nqn.2011-06.com.truenas:uuid:cef24057-8050-4fc7-ab87-773e19b32b0e:foo1/ctrl2/port
        if path.name.startswith('ctrl'):
            result = {}
            result['ctrl'] = int(path.name[4:])
            result['hostnqn'] = pathlib.Path(path, 'hostnqn').read_text().strip()
            result['host_traddr'] = pathlib.Path(path, 'host_traddr').read_text().strip()
            port_index = int(pathlib.Path(path, 'port').read_text().strip())
            result['port_id'] = port_index_to_id[port_index]
            return result

    @private
    def local_sessions(self, subsys_id=None):
        sessions = []
        global_info = self.middleware.call_sync('nvmet.global.config')
        subsystems = self.middleware.call_sync('nvmet.subsys.query')
        ports = self.middleware.call_sync('nvmet.port.query')
        ha = self.middleware.call_sync('failover.licensed')

        if global_info['kernel']:
            nvmet_debug_path = pathlib.Path(NVMET_DEBUG_DIR)
            if not nvmet_debug_path.exists():
                return sessions

            port_index_to_id = {port['index']: port['id'] for port in ports}

            if subsys_id is None:
                subsys_name_to_subsys_id = {subsys['subnqn']: subsys['id'] for subsys in subsystems}
                for subsys in nvmet_debug_path.iterdir():
                    if subsys_id := subsys_name_to_subsys_id.get(subsys.name):
                        for ctrl in subsys.iterdir():
                            if session := self.__parse_session_dir(ctrl, port_index_to_id):
                                session['subsys_id'] = subsys_id
                                sessions.append(session)
            else:
                for subsys in subsystems:
                    if subsys['id'] == subsys_id:
                        subnqn = subsys['subnqn']
                        path = nvmet_debug_path / subnqn
                        if path.is_dir():
                            for ctrl in path.iterdir():
                                if session := self.__parse_session_dir(ctrl, port_index_to_id):
                                    session['subsys_id'] = subsys_id
                                    sessions.append(session)
        else:
            if not self.middleware.call_sync('nvmet.spdk.nvmf_ready'):
                return sessions
            client = make_client()
            choices = {}
            port_to_portid = {}
            for port in ports:
                addr = port['addr_traddr']
                trtype = port['addr_trtype']
                addrs = [addr]
                if ha:
                    try:
                        mychoices = choices[trtype]
                    except KeyError:
                        mychoices = self.middleware.call_sync('nvmet.port.transport_address_choices', trtype, True)
                        mychoices[trtype] = mychoices
                    if pair := mychoices.get(addr, '').split('/'):
                        addrs.extend(pair)

                for addr in addrs:
                    port_to_portid[f"{trtype}:{addr}:{port['addr_trsvcid']}"] = port['id']
            for subsys in subsystems:
                if subsys_id is not None and subsys_id != subsys['id']:
                    continue
                for entry in nvmf_subsystem_get_qpairs(client, subsys['subnqn']):
                    laddr = entry['listen_address']
                    key = f"{laddr['trtype']}:{laddr['traddr']}:{laddr['trsvcid']}"
                    if port_id := port_to_portid.get(key):
                        session = {
                            'host_traddr': entry.get('peer_address', {}).get('traddr'),
                            'hostnqn': entry['hostnqn'],
                            'subsys_id': subsys['id'],
                            'port_id': port_id,
                            'ctrl': entry['cntlid']
                        }
                        # Do we really care that we might have multiple duplicate connections
                        # (only visible delta being a different qid and peer_address.trsvcid)
                        # If so, replace this with a simple append.
                        if session not in sessions:
                            sessions.append(session)

        return sessions

    @private
    async def load_kernel_modules(self):
        if (await self.config())['kernel']:
            if await self.middleware.call('failover.is_single_master_node') or \
               await self.middleware.call('nvmet.global.ana_active'):
                modules = await self.__kernel_modules()
                await self.middleware.run_in_thread(load_modules, modules)

    @private
    async def unload_kernel_modules(self):
        if modules := await self.__kernel_modules(True):
            modules.reverse()
            for m in modules:
                await self.middleware.run_in_thread(unload_module, m)

    async def __kernel_modules(self, all_modules=None):
        if (await self.config())['kernel']:
            modules = ['nvmet', 'nvmet_tcp']
            if all_modules or await self.middleware.call('nvmet.global.rdma_enabled'):
                modules.append('nvmet_rdma')
            return modules

    @private
    async def running(self):
        if (await self.config())['kernel']:
            return await self.middleware.run_in_thread(nvmet_kernel_module_loaded)
        else:
            return await self.middleware.call('service.started', NVMF_SERVICE)

    @private
    async def reload(self):
        if await self.running():
            await self._service_change('nvmet', 'reload')

    @private
    async def start(self):
        if (await self.config())['kernel']:
            await self.middleware.call('nvmet.global.load_kernel_modules')
        else:
            await self.middleware.call('nvmet.spdk.slots')
            if await self.middleware.call('service.start', NVMF_SERVICE):
                await self.middleware.call('nvmet.spdk.wait_nvmf_ready')
        await self.middleware.call('etc.generate', 'nvmet')

    @private
    async def stop(self):
        if await self.running():
            if (await self.config())['kernel']:
                await self.middleware.run_in_thread(clear_config)
                await self.middleware.call('nvmet.global.unload_kernel_modules')
            else:
                return await self.middleware.call('service.stop', NVMF_SERVICE)

    @private
    async def system_ready(self):
        # Because the kernel nvmet service does not have a systemd unit
        # we need to ensure it gets started (if necessary).
        service = await self.middleware.call('service.query',
                                             [['service', '=', NVMET_SERVICE_NAME]],
                                             {'get': True})
        if not service['enable'] or service['state'] == 'RUNNING':
            return

        if await self.middleware.call('failover.licensed'):
            return

        await self.middleware.call('nvmet.global.start')


async def __event_system_ready(middleware, event_type, args):
    await middleware.call('nvmet.global.system_ready')


async def pool_post_import(middleware, pool):
    if pool is None:
        return

    if await middleware.call('nvmet.global.running'):
        path = pool.get('path', '')
        name = pool.get('name', '')
        if await middleware.call('nvmet.namespace.query', [
            ('OR', [
                ('device_path', '^', f'zvol/{name}/'),
                ('device_path', '^', f'{path}/'),])]):
            await (await middleware.call('service.control', 'RELOAD', NVMET_SERVICE_NAME)).wait(raise_error=True)


async def setup(middleware):
    middleware.register_hook("pool.post_import", pool_post_import, sync=True)
    if await middleware.call('system.ready'):
        await middleware.call('iscsi.auth.load_upgrade_alerts')
    else:
        middleware.event_subscribe('system.ready', __event_system_ready)
