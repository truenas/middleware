import pathlib

import middlewared.sqlalchemy as sa
from middlewared.api import api_method
from middlewared.api.current import (NVMetGlobalAnaEnabledArgs, NVMetGlobalAnaEnabledResult, NVMetGlobalEntry,
                                     NVMetGlobalRDMAEnabledArgs, NVMetGlobalRDMAEnabledResult, NVMetGlobalSessionsArgs,
                                     NVMetGlobalSessionsResult, NVMetGlobalUpdateArgs, NVMetGlobalUpdateResult)
from middlewared.plugins.rdma.constants import RDMAprotocols
from middlewared.service import SystemServiceService, ValidationErrors, private
from middlewared.utils import filter_list
from .constants import NVMET_SERVICE_NAME
from .kernel import clear_config, load_modules, nvmet_kernel_module_loaded, unload_module
from .mixin import NVMetStandbyMixin
from .utils import uuid_nqn

NVMET_DEBUG_DIR = '/sys/kernel/debug/nvmet'


class NVMetGlobalModel(sa.Model):
    __tablename__ = 'services_nvmet_global'

    id = sa.Column(sa.Integer(), primary_key=True)
    nvmet_global_basenqn = sa.Column(sa.String(255), default=uuid_nqn())
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
        cli_namespace = 'sharing.nvmet.global'
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
        # if not await self.middleware.call('system.is_enterprise'):
        #     return True
        if not await self.middleware.call('failover.licensed'):
            return True
        return False

    async def __validate(self, verrors, data, schema_name, old=None):
        if not data.get('kernel', False):
            verrors.add(f'{schema_name}.kernel', 'Cannot disable kernel mode.')
        if data['rdma'] and old['rdma'] != data['rdma']:
            available_rdma_protocols = await self.middleware.call('rdma.capable_protocols')
            if RDMAprotocols.NVME.value not in available_rdma_protocols:
                verrors.add(
                    f'{schema_name}.rdma',
                    "This platform cannot support NVMe-oF(RDMA) or is missing a RDMA capable NIC."
                )
        if old['ana'] != data['ana']:
            if data['ana'] and await self.__ana_forbidden():
                verrors.add(
                    f'{schema_name}.ana',
                    "This platform does not support Asymmetric Namespace Access(ANA)."
                )

    @api_method(
        NVMetGlobalAnaEnabledArgs,
        NVMetGlobalAnaEnabledResult,
        roles=['SHARING_NVME_TARGET_READ']
    )
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

    @api_method(
        NVMetGlobalRDMAEnabledArgs,
        NVMetGlobalRDMAEnabledResult,
        roles=['SHARING_NVME_TARGET_READ']
    )
    async def rdma_enabled(self):
        """
        Returns whether RDMA is enabled or not.
        """
        if not await self.middleware.call('system.is_enterprise'):
            return False

        return (await self.middleware.call('nvmet.global.config'))['rdma']

    @api_method(
        NVMetGlobalSessionsArgs,
        NVMetGlobalSessionsResult,
        roles=['SHARING_NVME_TARGET_READ']
    )
    async def sessions(self, filters, options):
        sessions = []
        subsys_id = None
        for filter in filters:
            if len(filter) == 3 and filter[0] == 'subsys_id' and filter[1] == '=':
                subsys_id = filter[2]
                break
        sessions = await self.middleware.call('nvmet.global.local_sessions', subsys_id)
        if await self.ana_enabled():
            sessions.extend(await self.middleware.call('failover.call_remote',
                                                       'nvmet.global.local_sessions',
                                                       [subsys_id]))

        return filter_list(sessions, filters, options)

    def __parse_session_dir(self, path: pathlib.Path, port_index_to_id: dict):
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

        port_index_to_id = {port['index']: port['id'] for port in self.middleware.call_sync('nvmet.port.query')}

        if subsys_id is None:
            basenqn = global_info['basenqn']
            subsys_name_to_subsys_id = {f'{basenqn}:{subsys["name"]}': subsys['id'] for subsys in subsystems}
            for subsys in pathlib.Path(NVMET_DEBUG_DIR).iterdir():
                if subsys_id := subsys_name_to_subsys_id.get(subsys.name):
                    for ctrl in subsys.iterdir():
                        if session := self.__parse_session_dir(ctrl, port_index_to_id):
                            session['subsys_id'] = subsys_id
                            sessions.append(session)
        else:
            for subsys in subsystems:
                if subsys['id'] == subsys_id:
                    subnqn = f'{global_info["basenqn"]}:{subsys["name"]}'
                    path = pathlib.Path(NVMET_DEBUG_DIR, subnqn)
                    if path.is_dir():
                        for ctrl in path.iterdir():
                            if session := self.__parse_session_dir(ctrl, port_index_to_id):
                                session['subsys_id'] = subsys_id
                                sessions.append(session)

        return sessions

    @private
    async def load_kernel_modules(self):
        if (await self.config())['kernel']:
            do_load = any([
                await self.middleware.call('failover.status') in ['MASTER', 'SINGLE'],
                await self.middleware.call('nvmet.global.ana_active')
            ])
            if do_load:
                modules = await self.__kernel_modules()
                await self.middleware.run_in_thread(load_modules, modules)

    @private
    async def unload_kernel_modules(self):
        modules = await self.__kernel_modules()
        modules.reverse()
        for m in modules:
            await self.middleware.run_in_thread(unload_module, m)

    async def __kernel_modules(self):
        if (await self.config())['kernel']:
            modules = ['nvmet', 'nvmet_tcp']
            if await self.middleware.call('nvmet.global.rdma_enabled'):
                modules.append('nvmet_rdma')
            return modules

    @private
    async def running(self):
        if (await self.config())['kernel']:
            return await self.middleware.run_in_thread(nvmet_kernel_module_loaded)
        else:
            return False

    @private
    async def start(self):
        await self.middleware.call('nvmet.global.load_kernel_modules')
        await self.middleware.call("etc.generate", "nvmet")

    @private
    async def stop(self):
        if await self.running():
            await self.middleware.run_in_thread(clear_config)
            await self.middleware.call('nvmet.global.unload_kernel_modules')
