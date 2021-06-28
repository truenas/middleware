import asyncio
import errno

from collections import defaultdict

from middlewared.schema import Dict, Int, List, Str, returns
from middlewared.service import accepts, CallError, job, private, Service

from .utils import SCALEABLE_RESOURCES


class ChartReleaseService(Service):

    class Config:
        namespace = 'chart.release'

    @accepts()
    @returns(Dict(
        *[Str(r.name, enum=[r.name]) for r in SCALEABLE_RESOURCES],
    ))
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
    @returns(Dict(
        'scale_chart_release',
        Dict(
            'before_scale',
            *[Dict(r.value, additional_attrs=True) for r in SCALEABLE_RESOURCES],
            required=True
        ),
        Dict(
            'after_scale',
            *[Dict(r.value, additional_attrs=True) for r in SCALEABLE_RESOURCES],
            required=True
        ),
    ))
    @job(lock=lambda args: f'{args[0]}_chart_release_scale')
    async def scale(self, job, release_name, options):
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
        job.set_progress(20, f'Scaling workload(s) to {options["replica_count"]!r} replica(s)')
        try:
            await self.scale_release_internal(resources, options['replica_count'])
        except Exception:
            # This is a best effort to get relevant workloads back to replica count which they were on before
            await self.scale_release_internal(resources, replica_counts=replica_counts)
            raise
        else:
            desired_pods_count = sum(
                len(replica_counts[r.value]) * options['replica_count'] for r in SCALEABLE_RESOURCES
            )
            job.set_progress(40, f'Waiting for pods to be scaled to {desired_pods_count!r} replica(s)')
            while await self.middleware.call(
                'k8s.pod.query', [
                    ['metadata.namespace', '=', release['namespace']],
                    ['status.phase', 'in', ['Running', 'Pending']],
                ], {'count': True}
            ) != desired_pods_count:
                await asyncio.sleep(5)

        job.set_progress(100, f'Scaled workload(s) successfully to {options["replica_count"]!r} replica(s)')

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
    @returns()
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
    async def wait_for_pods_to_terminate(self, namespace, extra_filters=None):
        # wait for release to uninstall properly, helm right now does not support a flag for this but
        # a feature request is open in the community https://github.com/helm/helm/issues/2378
        while await self.middleware.call(
            'k8s.pod.query', [
                ['metadata.namespace', '=', namespace],
                ['status.phase', 'in', ['Running', 'Pending']],
            ] + (extra_filters or [])
        ):
            await asyncio.sleep(5)

    @private
    async def get_workload_to_pod_mapping(self, namespace):
        mapping = {'replicaset': defaultdict(dict), 'pod': defaultdict(dict)}
        for key in ('replicaset', 'pod'):
            for r in await self.middleware.call(
                f'k8s.{key}.query', [
                    ['metadata.namespace', '=', namespace],
                    ['metadata', 'rin', 'owner_references'],
                ], {'select': ['metadata']}
            ):
                for owner_reference in filter(lambda o: o.get('uid'), r['metadata']['owner_references'] or []):
                    mapping[key][owner_reference['uid']][r['metadata']['uid']] = r

        pod_mapping = defaultdict(list)
        for parent, replicasets in mapping['replicaset'].items():
            for replicaset in map(lambda r: mapping['replicaset'][parent][r], replicasets):
                if replicaset['metadata']['uid'] not in mapping['pod']:
                    continue
                pod_mapping[parent].extend([
                    p['metadata']['name'] for p in mapping['pod'][replicaset['metadata']['uid']].values()
                ])

        return pod_mapping
