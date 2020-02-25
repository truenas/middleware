import glob
import os

from middlewared.service import Service
from middlewared.utils import filter_list

from .global_base import GlobalActionsBase


class ISCSIGlobalService(Service, GlobalActionsBase):

    class Config:
        datastore_extend = 'iscsi.global.config_extend'
        datastore_prefix = 'iscsi_'
        service = 'iscsitarget'
        service_model = 'iscsitargetglobalconfiguration'
        namespace = 'iscsi.global'

    def sessions(self, filters, options):
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
                session_dict = {
                    'initiator': session,
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
                    'iser': None,  # FIXME: Implement me and offload please, look at initiator_alias too please
                    'offload': None,
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

    def alua_enabled(self):
        raise NotImplementedError()

    def terminate_luns_for_pool(self, pool_name):
        raise NotImplementedError()
