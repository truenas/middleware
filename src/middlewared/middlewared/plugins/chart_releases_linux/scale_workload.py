from middlewared.schema import Dict, Int, Str
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
        return {r.name for r in SCALEABLE_RESOURCES}

    @accepts(
        Str('release_name'),
        Dict(
            'scale_options',
            Int('replica_count', required=True),
        )
    )
    async def scale(self, release_name, options):
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
    async def scale_release_internal(self, resources, replicas=None, replica_counts=None):
        if replicas is not None and replica_counts:
            raise CallError('Only one of "replicas" or "replica_counts" should be specified')
        elif replicas is None and not replica_counts:
            raise CallError('Either one of "replicas" or "replica_counts" must be specified')

        assert bool(resources or replica_counts) is True

        replica_counts = replica_counts or {r.value: {} for r in SCALEABLE_RESOURCES}

        for resource in SCALEABLE_RESOURCES:
            for workload in resources[resource.value]:
                replica_count = replica_counts[resource.value].get(
                    workload['metadata']['name'], {}
                ).get('replicas') or replicas

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
