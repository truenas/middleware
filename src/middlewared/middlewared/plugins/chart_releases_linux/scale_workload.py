import asyncio
import errno

from collections import defaultdict

from middlewared.schema import Dict, Int, List, Str
from middlewared.service import accepts, CallError, private, Service

from .utils import Resources


SCALEABLE_RESOURCES = [
    Resources.DEPLOYMENT,
    Resources.STATEFULSET,
]


class ChartReleaseService(Service):

    class Config:
        namespace = 'chart.release'

    @accepts()
    async def scaleable_resources(self):
        """
        Returns choices for types of workloads which can be scaled up/down.
        """
        return {r.name: r.name for r in SCALEABLE_RESOURCES}

    @accepts(
        Str('release_name'),
        Dict(
            'scale_options',
            Int('replica_count', required=True),
        )
    )
    async def scale(self, release_name, options):
        """
        Scale a `release_name` chart release to `scale_options.replica_count` specified.

        This will scale deployments/statefulset to replica count specified.
        """
        await self.middleware.call('kubernetes.validate_k8s_setup')
        release = await self.middleware.call(
            'chart.release.query', [['id', '=', release_name]], {'get': True, 'extra': {'retrieve_resources': True}}
        )
        resources = release['resources']
        replica_counts = await self.get_replica_count_for_resources(resources)

        try:
            await self.scale_release_internal(resources, options['replica_count'])
        except Exception:
            # This is a best effort to get relevant workloads back to replica count which they were on before
            await self.scale_release_internal(resources, replica_counts=replica_counts)

        return {
            'before_scale': replica_counts,
            'after_scale': await self.get_replica_count_for_resources(
                (await self.middleware.call(
                    'chart.release.query', [['id', '=', release_name]],
                    {'get': True, 'extra': {'retrieve_resources': True}}
                ))['resources']
            )
        }

    @private
    async def get_replica_count_for_resources(self, resources):
        replica_counts = {r.value: {} for r in SCALEABLE_RESOURCES}
        for resource in SCALEABLE_RESOURCES:
            for workload in resources[resource.value]:
                replica_counts[resource.value][workload['metadata']['name']] = {
                    'replicas': workload['spec']['replicas'],
                }

        return replica_counts

    @private
    async def scale_release_internal(self, resources, replicas=None, replica_counts=None, resource_check=False):
        if replicas is not None and replica_counts:
            raise CallError('Only one of "replicas" or "replica_counts" should be specified')
        elif replicas is None and not replica_counts:
            raise CallError('Either one of "replicas" or "replica_counts" must be specified')

        assert bool(resources or replica_counts) is True

        replica_counts = replica_counts or {r.value: {} for r in SCALEABLE_RESOURCES}
        if resource_check:
            resources_data = {
                r.name.lower(): {
                    w['metadata']['name'] for w in await self.middleware.call(f'k8s.{r.name.lower()}.query')
                }
                for r in SCALEABLE_RESOURCES
            }

        for resource in SCALEABLE_RESOURCES:
            for workload in resources[resource.value]:
                replica_count = replica_counts[resource.value].get(
                    workload['metadata']['name'], {}
                ).get('replicas') or replicas

                if resource_check:
                    if workload['metadata']['name'] not in resources_data[resource.name.lower()]:
                        continue

                await self.middleware.call(
                    f'k8s.{resource.name.lower()}.update', workload['metadata']['name'], {
                        'namespace': workload['metadata']['namespace'],
                        'body': {
                            'spec': {
                                'replicas': replica_count,
                            }
                        }
                    }
                )

    @accepts(
        Str('release_name'),
        List(
            'workloads',
            items=[
                Dict(
                    'scale_workload',
                    Int('replica_count', required=True),
                    Str('type', enum=[r.name for r in SCALEABLE_RESOURCES], required=True),
                    Str('name', required=True),
                )
            ],
            empty=False,
        ),
    )
    async def scale_workloads(self, release_name, workloads):
        """
        Scale workloads in a chart release to specified `replica_count`.
        """
        release = await self.middleware.call(
            'chart.release.query', [['id', '=', release_name]], {'get': True, 'extra': {'retrieve_resources': True}}
        )

        not_found = {}
        scale_resources = {r.name: [] for r in SCALEABLE_RESOURCES}
        to_scale_resources = defaultdict(dict)

        for workload in workloads:
            to_scale_resources[workload['type']][workload['name']] = workload

        for scaleable_resource in SCALEABLE_RESOURCES:
            to_scale = to_scale_resources[scaleable_resource.name]
            if not to_scale:
                continue

            for resource in map(
                lambda r: r['metadata']['name'], release['resources'][f'{scaleable_resource.name.lower()}s']
            ):
                if resource in to_scale:
                    scale_resources[scaleable_resource.name].append(to_scale[resource])
                    to_scale.pop(resource)

            not_found.update(to_scale)

        if not_found:
            raise CallError(
                f'Unable to find {", ".join(not_found)} workload(s) for {release_name} release', errno=errno.ENOENT
            )

        for resource_type in scale_resources:
            for workload in scale_resources[resource_type]:
                await self.middleware.call(
                    f'k8s.{resource_type.lower()}.update', workload['name'], {
                        'namespace': release['namespace'],
                        'body': {'spec': {'replicas': workload['replica_count']}},
                    }
                )

    @private
    async def wait_for_pods_to_terminate(self, namespace):
        # wait for release to uninstall properly, helm right now does not support a flag for this but
        # a feature request is open in the community https://github.com/helm/helm/issues/2378
        while await self.middleware.call(
            'k8s.pod.query', [
                ['metadata.namespace', '=', namespace],
                ['status.phase', 'in', ['Running', 'Pending']],
            ]
        ):
            await asyncio.sleep(5)
