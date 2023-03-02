import os

from middlewared.service import Service


class K8sCRIService(Service):

    class Config:
        namespace = 'k8s.cri'
        private = True

    async def re_initialize(self):
        # We would be doing the following here:
        # 1) Remove old docker dataset
        # 2) Create new docker dataset
        # 3) Start docker
        # 4) Load bundled docker images
        # 5) Call it a day
        k8s_config = await self.middleware.call('kubernetes.config')
        docker_ds = os.path.join(k8s_config['dataset'], 'docker')
        if await self.middleware.call(
            'zfs.dataset.query', [['id', '=', docker_ds]], {
                'extra': {'retrieve_children': False, 'retrieve_properties': False}
            }
        ):
            await self.middleware.call('zfs.dataset.delete', docker_ds, {'recursive': True, 'force': True})

        await self.middleware.call('zfs.dataset.create', {'name': docker_ds, 'type': 'FILESYSTEM'})
        await self.middleware.call('zfs.dataset.mount', docker_ds)

        # start docker and load default images
        await self.middleware.call('service.start', 'docker')
        await self.middleware.call('container.image.load_default_images')

        await self.middleware.call('service.stop', 'docker')

    async def re_initialization_needed(self):
        started = await self.middleware.call('service.started', 'docker')
        if not started:
            await self.middleware.call('service.start', 'docker')
        try:
            return await self.middleware.call('container.image.query') == []
        finally:
            if started:
                await self.middleware.call('service.stop', 'docker')
