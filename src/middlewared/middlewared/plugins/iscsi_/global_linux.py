import glob
import os

from middlewared.schema import Bool, Dict, Int, Str
from middlewared.service import filterable, filterable_returns, private, Service
from middlewared.utils import filter_list, run


class ISCSIGlobalService(Service):

    class Config:
        datastore_extend = 'iscsi.global.config_extend'
        datastore_prefix = 'iscsi_'
        service = 'iscsitarget'
        service_model = 'iscsitargetglobalconfiguration'
        namespace = 'iscsi.global'

    @filterable
    @filterable_returns(Dict(
        'session',
        Str('initiator'),
        Str('initiator_addr'),
        Str('initiator_alias', null=True),
        Str('target'),
        Str('target_alias'),
        Str('header_digest', null=True),
        Str('data_digest', null=True),
        Int('max_data_segment_length', null=True),
        Int('max_receive_data_segment_length', null=True),
        Int('max_burst_length', null=True),
        Int('first_burst_length', null=True),
        Bool('immediate_data'),
        Bool('iser'),
        Bool('offload'),
    ))
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
    async def terminate_luns_for_pool(self, pool_name):
        if not await self.middleware.call('service.started', 'iscsitarget'):
            return

        g_config = await self.middleware.call('iscsi.global.config')
        targets = {t['id']: t for t in await self.middleware.call('iscsi.target.query')}
        extents = {t['id']: t for t in await self.middleware.call('iscsi.extent.query', [['enabled', '=', True]])}

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
