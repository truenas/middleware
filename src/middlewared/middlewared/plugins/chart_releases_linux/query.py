import collections
import copy
import itertools
import os

from middlewared.service import private, Service
from middlewared.utils import filter_list

from .utils import CHART_NAMESPACE_PREFIX, get_storage_class_name, Resources


class ChartReleaseService(Service):

    class Config:
        namespace = 'chart.release'

    @private
    async def query_releases(self, filters=None, options=None):
        if not await self.middleware.call('service.started', 'kubernetes'):
            return []

        k8s_config = await self.middleware.call('kubernetes.config')
        options = options or {}
        extra = copy.deepcopy(options.get('extra', {}))
        get_resources = extra.get('retrieve_resources')
        get_history = extra.get('history')

        if get_resources:
            storage_classes = collections.defaultdict(lambda: None)
            for storage_class in await self.middleware.call('k8s.storage_class.query'):
                storage_classes[storage_class['metadata']['name']] = storage_class

            resources = {r.value: collections.defaultdict(list) for r in Resources}

            for resource in Resources:
                for r_data in await self.middleware.call(
                    f'k8s.{resource.name.lower()}.query', [['metadata.namespace', '^', CHART_NAMESPACE_PREFIX]]
                ):
                    resources[resource.value][
                        r_data['metadata']['namespace'][len(CHART_NAMESPACE_PREFIX):]
                    ].append(r_data)

        release_secrets = await self.middleware.call('chart.release.releases_secrets', extra)
        releases = []
        for name, release in release_secrets.items():
            config = {}
            release_data = release['releases'].pop(0)
            cur_version = release_data['chart_metadata']['version']

            for rel_data in filter(
                lambda r: r['chart_metadata']['version'] == cur_version,
                itertools.chain(reversed(release['releases']), [release_data])
            ):
                config.update(rel_data['config'])

            release_data.update({
                'path': os.path.join('/mnt', k8s_config['dataset'], 'releases', name),
                'dataset': os.path.join(k8s_config['dataset'], 'releases', name),
                'config': config,
            })
            if get_resources:
                release_data['resources'] = {
                    'storage_class': storage_classes[get_storage_class_name(name)],
                    'host_path_volumes': await self.host_path_volumes(resources[Resources.POD.value][name]),
                    **{r.value: resources[r.value][name] for r in Resources},
                }
            if get_history:
                release_data['history'] = release['history']

            releases.append(release_data)

        return filter_list(releases, filters, options)

    @private
    async def host_path_volumes(self, pods):
        host_path_volumes = []
        for pod in pods:
            for volume in filter(lambda v: v.get('host_path'), pod['spec']['volumes']):
                host_path_volumes.append(copy.deepcopy(volume))

        return host_path_volumes
