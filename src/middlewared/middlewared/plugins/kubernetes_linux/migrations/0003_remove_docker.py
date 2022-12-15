import os


def migrate(middleware):
    k8s_config = middleware.call_sync('kubernetes.config')
    docker_ds = os.path.join(k8s_config['dataset'], 'docker')
    if middleware.call_sync(
        'zfs.dataset.query', [['id', '=', docker_ds]], {
            'extra': {'retrieve_children': False, 'retrieve_properties': False}
        }
    ):
        middleware.call_sync('zfs.dataset.delete', docker_ds, {'recursive': True, 'force': True})
