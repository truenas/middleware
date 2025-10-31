import collections

from middlewared.api import api_method
from middlewared.api.current import AppsIxVolumeEntry, AppsIxVolumeExistsArgs, AppsIxVolumeExistsResult
from middlewared.service import filterable_api_method, Service
from middlewared.utils.filter_list import filter_list

from .ix_apps.path import get_app_mounts_ds


class AppsIxVolumeService(Service):

    class Config:
        namespace = 'app.ix_volume'
        event_send = False
        cli_namespace = 'app.ix_volume'
        entry = AppsIxVolumeEntry

    @filterable_api_method(item=AppsIxVolumeEntry, roles=['APPS_READ'])
    async def query(self, filters, options):
        """
        Query ix-volumes with `filters` and `options`.
        """
        if not await self.middleware.call('docker.state.validate', False):
            return filter_list([], filters, options)

        docker_ds = (await self.middleware.call('docker.config'))['dataset']
        datasets = await self.middleware.call(
            'zfs.resource.query_impl',
            {
                'paths': [get_app_mounts_ds(docker_ds)],
                'get_children': True,
                'get_source': False,
                'properties': None
            }
        )
        apps = collections.defaultdict(list)
        for ds in filter(lambda x: x['name'].count('/') > 3, datasets):
            name_split = ds['name'].split('/', 4)
            apps[name_split[3]].append(name_split[-1])

        volumes = []
        for app, app_volumes in apps.items():
            for volume in app_volumes:
                volumes.append({
                    'name': volume,
                    'app_name': app,
                })

        return filter_list(volumes, filters, options)

    @api_method(AppsIxVolumeExistsArgs, AppsIxVolumeExistsResult, roles=['APPS_READ'])
    async def exists(self, app_name):
        """
        Check if ix-volumes exist for `app_name`.
        """
        return bool(await self.query([['app_name', '=', app_name]]))
