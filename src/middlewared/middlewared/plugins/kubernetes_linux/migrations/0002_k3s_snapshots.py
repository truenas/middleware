import os

from middlewared.service import CallError


def migrate(middleware):
    k8s_config = middleware.call_sync('kubernetes.config')
    kubelet_ds = os.path.join(k8s_config['dataset'], 'k3s/kubelet')
    for snapshot in middleware.call_sync('zfs.snapshot.query', [['id', 'rin', f'{kubelet_ds}@']]):
        try:
            middleware.call_sync('zfs.snapshot.delete', snapshot['id'], {'recursive': True})
        except CallError as e:
            middleware.logger.error('Failed to delete %r snapshot: %r', snapshot['id'], e)
