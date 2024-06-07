import collections
import errno

from middlewared.plugins.reporting.stats_utils import get_kubernetes_pods_stats
from middlewared.schema import Bool, Dict, Int, List, Ref, Str, returns
from middlewared.service import accepts, CallError, job, private, Service
from middlewared.validators import Range

from .utils import CHART_NAMESPACE_PREFIX, get_namespace, Resources


class ChartReleaseService(Service):

    class Config:
        namespace = 'chart.release'

    @private
    async def retrieve_pod_with_containers(self, release_name, retrieve_active_pods=False):
        await self.middleware.call('kubernetes.validate_k8s_setup')
        release = await self.middleware.call(
            'chart.release.query', [['id', '=', release_name]], {'get': True, 'extra': {'retrieve_resources': True}}
        )
        choices = {}
        for pod in filter(
            lambda p: not retrieve_active_pods or (p and p.get('status', {}).get('phase') == 'Running'),
            release['resources']['pods']
        ):
            containers = []
            for container in (
                (pod['status'].get('containerStatuses') or []) + (pod['status'].get('initContainerStatuses') or [])
            ):
                containers.append(container['name'])
            if containers:
                choices[pod['metadata']['name']] = containers

        return choices

    @accepts(Str('release_name'))
    @returns(Dict(
        additional_attrs=True,
        example={'plex-d4559844b-zcgq9': ['plex']},
    ))
    async def pod_console_choices(self, release_name):
        """
        Returns choices for console access to a chart release.

        Output is a dictionary with names of pods as keys and containing names of containers which the pod
        comprises of.
        """
        return await self.retrieve_pod_with_containers(release_name, True)

    @accepts(Str('release_name'))
    @returns(Dict(
        additional_attrs=True,
        example={'plex-d4559844b-zcgq9': ['plex']},
    ))
    async def pod_logs_choices(self, release_name):
        """
        Returns choices for accessing logs of any container in any pod in a chart release.
        """
        return await self.retrieve_pod_with_containers(release_name)

    @private
    async def validate_pod_log_args(self, release_name, pod_name, container_name):
        choices = await self.pod_logs_choices(release_name)
        if pod_name not in choices:
            raise CallError(f'Unable to locate {pod_name!r} pod.', errno=errno.ENOENT)
        elif container_name not in choices[pod_name]:
            raise CallError(
                f'Unable to locate {container_name!r} container in {pod_name!r} pod.', errno=errno.ENOENT
            )

    @accepts(
        Str('release_name'),
        Dict(
            'options',
            Int('limit_bytes', default=None, null=True, validators=[Range(min_=1)]),
            Int('tail_lines', default=500, validators=[Range(min_=1)], null=True),
            Str('pod_name', required=True, empty=False),
            Str('container_name', required=True, empty=False),
        ),
        roles=['APPS_READ'],
    )
    @returns()
    @job(lock='chart_release_logs', pipes=['output'])
    def pod_logs(self, job, release_name, options):
        """
        Export logs of `options.container_name` container in `options.pod_name` pod in `release_name` chart release.

        `options.tail_lines` is an option to select how many lines of logs to retrieve for the said container. It
        defaults to 500. If set to `null`, it will retrieve complete logs of the container.

        `options.limit_bytes` is an option to select how many bytes to retrieve from the tail lines selected. If set
        to null ( which is the default ), it will not limit the bytes returned. To clarify, `options.tail_lines`
        is applied first and the required number of lines are retrieved and then `options.limit_bytes` is applied.

        Please refer to websocket documentation for downloading the file.
        """
        self.middleware.call_sync(
            'chart.release.validate_pod_log_args', release_name, options['pod_name'], options['container_name']
        )

        logs = self.middleware.call_sync(
            'k8s.pod.get_logs', options['pod_name'], options['container_name'], get_namespace(release_name),
            options['tail_lines'], options['limit_bytes']
        )
        job.pipes.output.w.write((logs or '').encode())

    @accepts()
    @returns(Dict(additional_attrs=True))
    async def nic_choices(self):
        """
        Available choices for NIC which can be added to a pod in a chart release.
        """
        return await self.middleware.call('interface.choices')

    @accepts(roles=['APPS_READ'])
    @returns(List(items=[Int('used_port')]))
    async def used_ports(self):
        """
        Returns ports in use by applications.
        """
        return sorted(list(set({
            port['port']
            for chart_release in await self.middleware.call('chart.release.query')
            for port in chart_release['used_ports']
        })))

    @accepts()
    @returns(List(items=[Ref('certificate_entry')]))
    async def certificate_choices(self):
        """
        Returns certificates which can be used by applications.
        """
        return await self.middleware.call(
            'certificate.query', [['revoked', '=', False], ['cert_type_CSR', '=', False], ['parsed', '=', True]],
            {'select': ['name', 'id']}
        )

    @accepts()
    @returns(List(items=[Ref('certificateauthority_entry')]))
    async def certificate_authority_choices(self):
        """
        Returns certificate authorities which can be used by applications.
        """
        return await self.middleware.call(
            'certificateauthority.query', [['revoked', '=', False], ['parsed', '=', True]], {'select': ['name', 'id']}
        )

    @accepts(Str('release_name'), roles=['APPS_READ'])
    @returns(Dict(
        Int('available', required=True),
        Int('desired', required=True),
        Str('status', required=True, enum=['ACTIVE', 'DEPLOYING', 'STOPPED'])
    ))
    async def pod_status(self, release_name):
        """
        Retrieve available/desired pods status for a chart release and it's current state.
        """
        status = {'available': 0, 'desired': 0}
        for resource in (Resources.DEPLOYMENT, Resources.STATEFULSET):
            for r_data in await self.middleware.call(
                f'k8s.{resource.name.lower()}.query', [['metadata.namespace', '=', get_namespace(release_name)]],
            ):
                # Detail about ready_replicas/replicas
                # https://stackoverflow.com/questions/66317251/couldnt-understand-availablereplicas-
                # readyreplicas-unavailablereplicas-in-dep
                status.update({
                    'available': (r_data['status'].get('readyReplicas') or 0),
                    'desired': (r_data['status'].get('replicas') or 0),
                })
        pod_diff = status['available'] - status['desired']
        r_status = 'ACTIVE'
        if pod_diff == 0 and status['desired'] == 0:
            r_status = 'STOPPED'
        elif pod_diff < 0:
            r_status = 'DEPLOYING'
        return {
            'status': r_status,
            **status,
        }

    @accepts(
        Dict(
            'options',
            Bool('resource_events', default=False),
            List('resources', enum=[r.name for r in Resources]),
            List('resource_filters'),
        )
    )
    @private
    async def get_resources_with_workload_mapping(self, options):
        resources_enum = [Resources[r] for r in options['resources']]
        resources = {r.value: collections.defaultdict(list) for r in resources_enum}
        workload_status = collections.defaultdict(lambda: {'desired': 0, 'available': 0})
        for resource in resources_enum:
            for r_data in await self.middleware.call(
                f'k8s.{resource.name.lower()}.query', options['resource_filters'], {
                    'extra': {'events': options['resource_events']}
                }
            ):
                release_name = r_data['metadata']['namespace'][len(CHART_NAMESPACE_PREFIX):]
                resources[resource.value][release_name].append(r_data)
                if resource in (Resources.DEPLOYMENT, Resources.STATEFULSET):
                    workload_status[release_name]['desired'] += (r_data['status'].get('replicas') or 0)
                    workload_status[release_name]['available'] += (r_data['status'].get('readyReplicas') or 0)

        return {'resources': resources, 'workload_status': workload_status}

    @private
    async def get_consumed_host_paths(self):
        apps = {}
        if not await self.middleware.call('kubernetes.validate_k8s_setup', False):
            return apps

        app_resources = collections.defaultdict(list)
        resources = await self.get_resources_with_workload_mapping({
            'resources': [Resources.DEPLOYMENT.name, Resources.STATEFULSET.name]
        })
        for resources_info in resources['resources'].values():
            for app_name in resources_info:
                app_resources[app_name].extend(resources_info[app_name])

        for app_name in app_resources:
            apps[app_name] = await self.middleware.call('chart.release.host_path_volumes', app_resources[app_name])

        return apps

    @private
    async def stats(self, release_name):
        chart_release = await self.middleware.call('chart.release.get_instance', release_name, {
            'extra': {'retrieve_resources': True, 'stats': False}
        })
        return await self.stats_internal(chart_release['resources']['pods'])

    @private
    async def stats_internal(self, pods, netdata_metrics=None):
        return get_kubernetes_pods_stats(
            [p['metadata']['name'] for p in pods],
            netdata_metrics or await self.middleware.call('netdata.get_chart_metrics', 'k3s_stats.k3s_stats')
        )
