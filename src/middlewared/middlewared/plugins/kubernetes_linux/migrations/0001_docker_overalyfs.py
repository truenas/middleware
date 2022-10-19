import os


def migrate(middleware):
    # We would be doing the following here:
    # 1) Remove old docker dataset
    # 2) Create new docker dataset
    # 3) Start docker
    # 4) Load bundled docker images
    # 5) Call it a day
    k8s_config = middleware.call_sync('kubernetes.config')
    docker_ds = os.path.join(k8s_config['dataset'], 'docker')
    if middleware.call_sync(
        'zfs.dataset.query', [['id', '=', docker_ds]], {
            'extra': {'retrieve_children': False, 'retrieve_properties': False}
        }
    ):
        middleware.call_sync('zfs.dataset.delete', docker_ds, {'recursive': True, 'force': True})

    middleware.call_sync('zfs.dataset.create', {'name': docker_ds, 'type': 'FILESYSTEM'})
    middleware.call_sync('zfs.dataset.mount', docker_ds)

    # start docker and load default images
    middleware.call_sync('service.start', 'docker')
    middleware.call_sync('container.image.load_default_images')

    middleware.call_sync('service.stop', 'docker')
