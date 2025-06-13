import glob
import os
from contextlib import suppress

from middlewared.api import api_method
from middlewared.api.current import ISCSIGlobalSessionsArgs, ISCSIGlobalSessionsResult
from middlewared.service import private, Service
from middlewared.service_exception import MatchNotFound
from middlewared.utils import filter_list, run


class ISCSIGlobalService(Service):

    class Config:
        namespace = 'iscsi.global'

    @api_method(
        ISCSIGlobalSessionsArgs,
        ISCSIGlobalSessionsResult,
        roles=['SHARING_ISCSI_GLOBAL_READ']
    )
    def sessions(self, filters, options):
        """
        Get a list of currently running iSCSI sessions. This includes initiator and target names
        and the unique connection IDs.
        """
        sessions = []
        global_info = self.middleware.call_sync('iscsi.global.config')
        base_path = '/sys/kernel/scst_tgt/targets/iscsi'
        for target_dir in glob.glob(f'{base_path}/{global_info["basename"]}*'):
            target = target_dir.rsplit('/', 1)[-1]
            if target.startswith(f'{global_info["basename"]}:HA:'):
                continue
            for session in os.listdir(os.path.join(target_dir, 'sessions')):
                session_dir = os.path.join(target_dir, 'sessions', session)
                ip_file = glob.glob(f'{session_dir}/*/ip')
                if not ip_file:
                    continue

                # Initiator alias is another name sent by initiator but we are unable to retrieve it in scst
                session_dict = {
                    'initiator': session.rsplit('#', 1)[0],
                    'initiator_alias': None,
                    'target': target,
                    'target_alias': target.rsplit(':', 1)[-1],
                    'header_digest': None,
                    'data_digest': None,
                    'max_data_segment_length': None,
                    'max_receive_data_segment_length': None,
                    'max_xmit_data_segment_length': None,
                    'max_burst_length': None,
                    'first_burst_length': None,
                    'immediate_data': False,
                    'iser': False,
                    'offload': False,  # It is a chelsio NIC driver to offload iscsi, we are not using it so far
                }
                with open(ip_file[0], 'r') as f:
                    session_dict['initiator_addr'] = f.read().strip()
                transport = os.path.join(os.path.dirname(ip_file[0]), 'transport')
                with suppress(FileNotFoundError):
                    with open(transport, 'r') as f:
                        session_dict['iser'] = 'iSER' == f.read().strip()
                for k, f, op in (
                    ('header_digest', 'HeaderDigest', None),
                    ('data_digest', 'DataDigest', None),
                    ('max_burst_length', 'MaxBurstLength', lambda i: int(i)),
                    ('max_receive_data_segment_length', 'MaxRecvDataSegmentLength', lambda i: int(i)),
                    ('max_xmit_data_segment_length', 'MaxXmitDataSegmentLength', lambda i: int(i)),
                    ('first_burst_length', 'FirstBurstLength', lambda i: int(i)),
                    ('immediate_data', 'ImmediateData', lambda i: True if i == 'Yes' else False),
                ):
                    f_path = os.path.join(session_dir, f)
                    if os.path.exists(f_path):
                        with open(f_path, 'r') as fd:
                            data = fd.read().strip()
                            if data != 'None':
                                if op:
                                    data = op(data)
                                session_dict[k] = data

                # We get recv/emit data segment length, keeping consistent with freebsd, we can
                # take the maximum of two and show it for max_data_segment_length
                if session_dict['max_xmit_data_segment_length'] and session_dict['max_receive_data_segment_length']:
                    session_dict['max_data_segment_length'] = max(
                        session_dict['max_receive_data_segment_length'], session_dict['max_xmit_data_segment_length']
                    )

                sessions.append(session_dict)
        return filter_list(sessions, filters, options)

    @private
    def resync_readonly_property_for_zvol(self, id_, read_only_value):
        try:
            extent = self.middleware.call_sync(
                'iscsi.extent.query',
                [['enabled', '=', True], ['path', '=', f'zvol/{id_}']],
                {'get': True}
            )
            ro = True if read_only_value.lower() == 'on' else False
            if extent['ro'] != ro:
                self.middleware.call_sync('iscsi.extent.update', extent['id'], {'ro': ro})
        except MatchNotFound:
            return

    @private
    def resync_lun_size_for_zvol(self, id_):
        if not self.middleware.call_sync('service.started', 'iscsitarget'):
            return

        extent = self.middleware.call_sync(
            'iscsi.extent.query', [['enabled', '=', True], ['path', '=', f'zvol/{id_}']],
            {'select': ['name', 'enabled', 'path']}
        )
        if not extent:
            return

        try:
            # CORE ctl device names are incompatible with SCALE SCST
            # so (similarly to scst.mako.conf) replace period with underscore, slash with dash
            extent_name = extent[0]["name"].replace('.', '_').replace('/', '-')
            with open(f'/sys/kernel/scst_tgt/devices/{extent_name}/resync_size', 'w') as f:
                f.write('1')
        except Exception as e:
            if isinstance(e, OSError) and e.errno == 124:
                # 124 == Wrong medium type
                # This is raised when all the iscsi targets are removed causing /etc/scst.conf to
                # be written with a "blank" config. Once this occurs, any time a new iscsi target
                # is added and the size gets changed, it will raise this error. In my testing,
                # SCST sees the zvol size change and so does the initiator so it's safe to ignore.
                pass
            else:
                self.logger.warning('Failed to resync lun size for %r', extent[0]['name'], exc_info=True)

    @private
    def resync_lun_size_for_file(self, path):
        if not self.middleware.call_sync('service.started', 'iscsitarget'):
            return

        extent = self.middleware.call_sync(
            'iscsi.extent.query', [
                ['enabled', '=', True], ['type', '=', 'FILE'], ['path', '=', path]
            ], {'select': ['enabled', 'type', 'path', 'name']}
        )
        if not extent:
            return

        try:
            extent_name = extent[0]["name"].replace('.', '_')
            with open(f'/sys/kernel/scst_tgt/devices/{extent_name}/resync_size', 'w') as f:
                f.write('1')
        except Exception as e:
            if isinstance(e, OSError) and e.errno == 124:
                # 124 == Wrong medium type
                # This is raised when all the iscsi targets are removed causing /etc/scst.conf to
                # be written with a "blank" config. Once this occurs, any time a new iscsi target
                # is added and the size gets changed, it will raise this error. In my testing,
                # SCST sees the zvol size change and so does the initiator so it's safe to ignore.
                pass
            else:
                self.logger.warning('Failed to resync lun size for %r', extent[0]['name'], exc_info=True)

    @private
    async def terminate_luns_for_pool(self, pool_name):
        if not await self.middleware.call('service.started', 'iscsitarget'):
            return

        g_config = await self.middleware.call('iscsi.global.config')
        targets = {t['id']: t for t in await self.middleware.call('iscsi.target.query')}
        extents = {
            t['id']: t for t in await self.middleware.call(
                'iscsi.extent.query', [['enabled', '=', True]], {'select': ['enabled', 'path', 'id']}
            )
        }

        for associated_target in filter(
            lambda a: a['extent'] in extents and extents[a['extent']]['path'].startswith(f'zvol/{pool_name}/'),
            await self.middleware.call('iscsi.targetextent.query')
        ):
            self.middleware.logger.debug('Terminating associated target %r', associated_target['id'])
            cp = await run([
                'scstadmin', '-noprompt', '-rem_lun', str(associated_target['lunid']), '-driver',
                'iscsi', '-target', f'{g_config["basename"]}:{targets[associated_target["target"]]["name"]}',
                '-group', 'security_group'
            ], check=False)

            if cp.returncode:
                self.middleware.logger.error(
                    'Failed to remove associated target %r : %s', associated_target['id'], cp.stderr.decode()
                )
