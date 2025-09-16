import os
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Literal

import middlewared.sqlalchemy as sa
from middlewared.api import api_method
from middlewared.api.current import (FCPortPortChoicesArgs, FCPortPortChoicesResult, FCPortCreateArgs, FCPortCreateResult,
                                     FCPortDeleteArgs, FCPortDeleteResult, FCPortEntry, FCPortStatusArgs,
                                     FCPortStatusResult, FCPortUpdateArgs, FCPortUpdateResult)
from middlewared.plugins.failover_.remote import NETWORK_ERRORS
from middlewared.service import CallError, CRUDService, private, ValidationErrors
from middlewared.service_exception import MatchNotFound
from middlewared.utils import filter_list
from .fc.utils import naa_to_int, str_to_naa, wwn_as_colon_hex, wwpn_to_vport_naa

VPORT_SEP_CHAR = '/'
QLA2XXX_KERNEL_TARGET_MODULE = 'qla2x00tgt'
SCST_QLA_TARGET_PATH = '/sys/kernel/scst_tgt/targets/qla2x00t'


class FCPortModel(sa.Model):
    __tablename__ = 'services_fibrechanneltotarget'

    id = sa.Column(sa.Integer(), primary_key=True)
    fc_port = sa.Column(sa.String(40))
    fc_target_id = sa.Column(sa.ForeignKey('services_iscsitarget.id'), nullable=True, index=True)


class FCPortService(CRUDService):

    class Config:
        namespace = "fcport"
        datastore = "services.fibrechanneltotarget"
        datastore_prefix = 'fc_'
        datastore_extend_context = "fcport.extend_context"
        datastore_extend = 'fcport.extend'
        cli_namespace = "sharing.fc_port"
        entry = FCPortEntry
        role_prefix = 'SHARING_ISCSI_TARGET'

    @api_method(FCPortCreateArgs, FCPortCreateResult, audit='Create FC port mapping',
                audit_extended=lambda data: data['alias'])
    async def do_create(self, data: dict) -> dict:
        """
        Creates mapping between a FC port and a target.

        `port` is a FC host port `alias`, or `alias/number` for a NPIV port.

        `target_id` is the `id` of the target to be associated with the FC port.
        """
        await self._validate("fcport_create", data)

        await self.compress(data)

        orig_count = await self.count()

        pk = await self.middleware.call(
            'datastore.insert', self._config.datastore, data,
            {'prefix': self._config.datastore_prefix})

        await self.update_scst(orig_count == 0)

        return await self.get_instance(pk)

    @api_method(FCPortUpdateArgs, FCPortUpdateResult, audit='Update FC port mapping', audit_callback=True)
    async def do_update(self, audit_callback: callable, id_: int, data: dict) -> dict:
        """
        Update FC port mapping `id`.
        """
        old = await self.get_instance(id_)
        audit_callback(old['port'])
        # Reflatten target_id
        old['target_id'] = old.pop('target')['id']
        new = old.copy()
        new.update(data)

        await self._validate("fcport_update", new, id_)

        await self.compress(new)

        await self.middleware.call(
            "datastore.update",
            self._config.datastore,
            id_,
            new,
            {'prefix': self._config.datastore_prefix}
        )

        await self.update_scst()

        return await self.get_instance(id_)

    @api_method(FCPortDeleteArgs, FCPortDeleteResult, audit='Delete FC port mapping', audit_callback=True)
    async def do_delete(self, audit_callback: callable, id_: int) -> Literal[True]:
        """
        Delete FC port mapping `id`.
        """
        alias = (await self.get_instance(id_))['port']
        audit_callback(alias)

        response = await self.middleware.call(
            "datastore.delete",
            self._config.datastore,
            id_
        )

        await self.update_scst()

        return response

    @api_method(FCPortPortChoicesArgs, FCPortPortChoicesResult)
    async def port_choices(self, include_used):
        result = {}
        if include_used:
            # We don't need to check, so don't populate this
            used_ports = set()
        else:
            used_ports = set(e['port'] for e in await self.middleware.call('fcport.query', [], {'select': ['port']}))
        for fc_host in await self.middleware.call('fc.fc_host.query'):
            alias = fc_host['alias']
            if include_used or alias not in used_ports:
                result[alias] = {
                    'wwpn': fc_host['wwpn'],
                    'wwpn_b': fc_host['wwpn_b']
                }
            if fc_host['npiv']:
                int_wwpn = naa_to_int(fc_host['wwpn'])
                int_wwpn_b = naa_to_int(fc_host['wwpn_b'])
                for chan in range(1, fc_host['npiv'] + 1):
                    npiv_alias = f'{alias}/{chan}'
                    if include_used or npiv_alias not in used_ports:
                        result[npiv_alias] = {
                            'wwpn': wwpn_to_vport_naa(int_wwpn, chan),
                            'wwpn_b': wwpn_to_vport_naa(int_wwpn_b, chan)
                        }

        return result

    @private
    async def local_status(self, node, port, with_lun_access):
        """
        Query the status of the specified fcport on this node, or
        all fcports if None is specified.
        """
        if port:
            ports = await self.middleware.call('fcport.query', [['port', '=', port]])
        else:
            ports = await self.middleware.call('fcport.query')

        key = 'wwpn' if node == 'A' else 'wwpn_b'
        naa_to_fc_host = {str_to_naa(fc['port_name']): fc for fc in await self.middleware.call('fc.fc_hosts')}
        qla_target_path = Path(SCST_QLA_TARGET_PATH)
        result = {}
        for p in ports:
            naa = p[key]
            if naa is None:
                continue
            sessions_path = qla_target_path / wwn_as_colon_hex(naa) / 'sessions'
            sessions = []
            try:
                with os.scandir(sessions_path) as iterator:
                    for entry in iterator:
                        if not entry.is_dir():
                            continue
                        if with_lun_access:
                            have_lun = False
                            with os.scandir(Path(entry.path) / 'luns') as subdir:
                                for subentry in subdir:
                                    if subentry.name.isnumeric():
                                        have_lun = True
                                        break
                            if have_lun:
                                sessions.append(entry.name)
                        else:
                            sessions.append(entry.name)
            except FileNotFoundError:
                # In HA when ALUA is disabled this path will not exist
                result[p['port']] = {
                    'port_type': 'Unknown',
                    'port_state': 'Offline',
                    'speed': 'Unknown',
                    'physical': False,
                    key: naa,
                    'sessions': [],
                }
                continue
            # Take some data directly from fc.fc_hosts
            result[p['port']] = {
                'port_type': naa_to_fc_host[naa]['port_type'],
                'port_state': naa_to_fc_host[naa]['port_state'],
                'speed': naa_to_fc_host[naa]['speed'],
                'physical': naa_to_fc_host[naa]['physical'],
                key: naa,
                'sessions': sessions,
            }
        return result

    async def _get_remote_local_status(self, node, port, with_lun_access):
        try:
            return await self.middleware.call('failover.call_remote', 'fcport.local_status', [node, port, with_lun_access])
        except CallError as e:
            if e.errno in NETWORK_ERRORS + (CallError.ENOMETHOD,):
                # swallow error, but don't present any choices
                return []
            else:
                raise

    @api_method(FCPortStatusArgs, FCPortStatusResult, roles=['SHARING_ISCSI_TARGET_READ'])
    async def status(self, filters, options):
        with_lun_access = options['extra']['with_lun_access']
        # If a filter has been supplied, and if it *only* selects a single fc_port
        # then we can optimize what data we collect.
        if filters and len(filters) == 1 and len(filters[0]) == 3 and filters[0][0] == 'port' and filters[0][1] == '=':
            # Optimize
            query_port = filters[0][2]

        else:
            # Get all the data
            query_port = None

        if await self.middleware.call('failover.licensed'):
            node = await self.middleware.call('failover.node')
            match node:
                case 'A':
                    node_a_data = await self.middleware.call('fcport.local_status', node, query_port, with_lun_access)
                    node_b_data = await self._get_remote_local_status('B', query_port, with_lun_access)
                case 'B':
                    node_a_data = await self._get_remote_local_status('A', query_port, with_lun_access)
                    node_b_data = await self.middleware.call('fcport.local_status', node, query_port, with_lun_access)
                case _:
                    raise CallError(f'Unknown node: {node}')
        else:
            node_a_data = await self.middleware.call('fcport.local_status', 'A', query_port, with_lun_access)
            node_b_data = []

        # Merge the data
        port_2_data = defaultdict(dict)
        for port in node_a_data:
            port_2_data[port]['A'] = node_a_data[port]
            port_2_data[port]['port'] = port
        for port in node_b_data:
            port_2_data[port]['B'] = node_b_data[port]
            port_2_data[port]['port'] = port

        return filter_list(port_2_data.values(), filters, options)

    async def _validate(self, schema_name: str, data: dict, id_: int = None):
        verrors = ValidationErrors()
        # Make sure we don't reuse port.
        await self._ensure_unique(verrors, schema_name, 'port', data['port'], id_)

        # We are allowed to reuse the target_id, but only once per physical port
        # i.e. fc0 and fc1/3 would be a valid combination, but fc1 and fc1/3 would not.
        filters = [['target.id', '=', data['target_id']]]
        if id_ is not None:
            filters.append(['id', '!=', id_])
        ports = [fcp['port'] for fcp in await self.middleware.call('fcport.query', filters)]
        ports_set = {fcp.split('/')[0] for fcp in ports}

        if data['port'].split('/')[0] in ports_set:
            verrors.add(
                f'{schema_name}.port',
                f'Invalid FC port ({data["port"]}) supplied, target already mapped to {",".join(ports)}'
            )

        # Make sure that the port base is a valid fc_host alias
        fc_hosts = {host['alias']: host for host in await self.middleware.call('fc.fc_host.query')}
        port = data.get('port')
        if port:
            if VPORT_SEP_CHAR in port:
                # NPIV - Get the base FC Host
                fc_host_alias, chan = port.rsplit(VPORT_SEP_CHAR, 1)
            else:
                fc_host_alias = port
                chan = None
            if fc_host_alias in fc_hosts:
                # Valid base, may need to check NPIV chan
                if chan is not None:
                    if chan.isdigit():
                        npiv_setting = fc_hosts[fc_host_alias]['npiv']
                        if int(chan) > npiv_setting:
                            verrors.add(
                                f'{schema_name}.port',
                                f'Invalid FC port ({port}) supplied, chan {chan} is greater than NPIV setting {npiv_setting}'
                            )
                        elif int(chan) == 0:
                            verrors.add(
                                f'{schema_name}.port',
                                f'Invalid FC port ({port}) supplied, chan {chan} must be greater than 0 and less than NPIV setting {npiv_setting}'
                            )
                    else:
                        verrors.add(
                            f'{schema_name}.port',
                            f'Invalid FC port ({port}) supplied, digits only after "{VPORT_SEP_CHAR}"'
                        )
            else:
                verrors.add(
                    f'{schema_name}.port',
                    f'Invalid FC port ({port}) supplied, should be one of: {",".join(fc_hosts.keys())}'
                )
        else:
            verrors.add(
                f'{schema_name}.port',
                f'No FC port supplied, should be based on one of: {",".join(fc_hosts.keys())}'
            )

        # Test the target supplied
        target_id = data.get('target_id')
        if target_id is not None:
            try:
                target = await self.middleware.call('iscsi.target.query', [['id', '=', target_id]], {'get': True})
            except MatchNotFound:
                verrors.add(
                    f'{schema_name}.target_id',
                    f'No target exists with the specified id {target_id}'
                )
            else:
                target_mode = target['mode']
                if target_mode not in ['FC', 'BOTH']:
                    target_name = target['name']
                    verrors.add(
                        f'{schema_name}.target_id',
                        f'Specified target "{target_name}" ({target_id}) does not have a "mode" ({target_mode}) that permits FC access'
                    )

        verrors.check()

    @private
    async def compress(self, data):
        for key in ['wwpn', 'wwpn_b']:
            if key in data:
                data.pop(key)
        return data

    @private
    async def extend_context(self, rows, extra):
        return {
            "fc.fc_host.query": await self.middleware.call('fc.fc_host.query')
        }

    @private
    async def extend(self, data, context):
        data['wwpn'] = None
        data['wwpn_b'] = None
        # We want to retrieve the WWPN associated with the port name
        if VPORT_SEP_CHAR in data['port']:
            # NPIV - Get the base FC Host
            fc_host_alias, chan = data['port'].rsplit(VPORT_SEP_CHAR, 1)
        else:
            fc_host_alias = data['port']
            chan = None
        try:
            fc_host_pair = filter_list(context['fc.fc_host.query'], [('alias', '=', fc_host_alias)], {'get': True})
        except MatchNotFound:
            pass
        else:
            if chan:
                # NPIV
                data['wwpn'] = wwpn_to_vport_naa(fc_host_pair.get('wwpn'), int(chan))
                data['wwpn_b'] = wwpn_to_vport_naa(fc_host_pair.get('wwpn_b'), int(chan))
            else:
                # Non-NPIV
                data['wwpn'] = fc_host_pair.get('wwpn')
                data['wwpn_b'] = fc_host_pair.get('wwpn_b')
        return data

    @private
    async def get_options(self, options):
        # Override superclass method called by query in order to add a side effect
        await self.middleware.call('fc.fc_host.ensure_wired')
        return await super().get_options(options)

    @private
    async def count(self):
        return await self.middleware.call(
            "datastore.query",
            self._config.datastore,
            [],
            {'count': True}
        )

    def __load_kernel_module(self):
        # If SCST has already started, but the kernel target module is not already loaded
        if os.path.isdir('/sys/kernel/scst_tgt/targets') and not os.path.isdir('/sys/kernel/scst_tgt/targets/qla2x00t'):
            self.logger.info('Loading kernel module %r', QLA2XXX_KERNEL_TARGET_MODULE)
            try:
                subprocess.run(["modprobe", QLA2XXX_KERNEL_TARGET_MODULE])
            except subprocess.CalledProcessError as e:
                self.logger.error('Failed to load kernel module. Error %r', e)

    @private
    async def load_kernel_module(self):
        """
        Load the Fibre Channel kernel target module.
        """
        await self.middleware.run_in_thread(self.__load_kernel_module)

    @private
    async def update_scst(self, do_module_load=False):
        # First process the local (MASTER) config
        if do_module_load:
            await self.middleware.run_in_thread(self.__load_kernel_module)

        await self._service_change('iscsitarget', 'reload', options={'ha_propagate': False})

        # Then process the BACKUP config if we are HA and ALUA is enabled.
        if await self.middleware.call("iscsi.global.alua_enabled") and await self.middleware.call('failover.remote_connected'):
            if do_module_load:
                await self.middleware.call('failover.call_remote', 'fcport.load_kernel_module')
            await self.middleware.call('failover.call_remote', 'service.control', ['RELOAD', 'iscsitarget'],
                                       {'job': True})
            await self.middleware.call('iscsi.alua.wait_for_alua_settled')
