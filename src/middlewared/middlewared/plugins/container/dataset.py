from middlewared.service import CallError, private, Service

REGISTRY_URL = "http://pivnoy.thelogin.ru"


class ContainerService(Service):
    class Config:
        cli_namespace = 'service.container'
        namespace = 'container'
        role_prefix = 'CONTAINER'

    @private
    async def ensure_datasets(self, pool):
        main_dataset = f'{pool}/.truenas_containers'
        main_dataset_mountpoint = f'/.truenas_containers/{pool}'

        datasets = [f'{main_dataset}/containers', f'{main_dataset}/images']

        existing_datasets = set()
        for dataset in await self.middleware.call(
            'zfs.resource.query_impl',
            {'paths': [main_dataset] + datasets, 'properties': ['mountpoint']}
        ):
            if dataset['type'] != 'FILESYSTEM':
                raise CallError(f'Expected dataset {dataset["name"]!r} to be FILESYSTEM, but it is {dataset["type"]}')

            if dataset['name'] == main_dataset:
                main_dataset_mountpoint_value = f'/mnt{main_dataset_mountpoint}'
                if dataset['properties']['mountpoint']['value'] != main_dataset_mountpoint_value:
                    raise CallError(
                        f'Expected dataset {dataset["name"]} to have mountpoint of {main_dataset_mountpoint_value!r}, '
                        f'but it is {dataset["properties"]["mountpoint"]["value"]!r}.'
                    )

            existing_datasets.add(dataset['name'])

        if main_dataset not in existing_datasets:
            await self.middleware.call(
                'zfs.dataset.create',
                {
                    'name': main_dataset,
                    'type': 'FILESYSTEM',
                    'properties': {'mountpoint': main_dataset_mountpoint},
                },
            )

        for dataset in datasets:
            if dataset not in existing_datasets:
                await self.middleware.call(
                    'zfs.dataset.create',
                    {
                        'name': dataset,
                        'type': 'FILESYSTEM',
                    },
                )
