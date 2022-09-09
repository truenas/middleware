import collections
import errno
import os

from middlewared.schema import Bool, Dict, Int, List, Ref, Str, returns
from middlewared.service import accepts, CallError, job, private, Service
from middlewared.validators import Range

from .utils import CHART_NAMESPACE_PREFIX, get_namespace, get_storage_class_name, Resources


class ChartReleaseService(Service):

    class Config:
        namespace = 'chart.release'

    @private
    async def retrieve_pod_with_containers(self, release_name):
        await self.middleware.call('kubernetes.validate_k8s_setup')
        release = await self.middleware.call(
            'chart.release.query', [['id', '=', release_name]], {'get': True, 'extra': {'retrieve_resources': True}}
        )
        choices = {}
        for pod in release['resources']['pods']:
            choices[pod['metadata']['name']] = []
            for container in (
                (pod['status']['container_statuses'] or []) + (pod['status']['init_container_statuses'] or [])
            ):
                choices[pod['metadata']['name']].append(container['name'])

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
        return await self.retrieve_pod_with_containers(release_name)

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
            Int('limit_bytes', default=None, null=True, validators=[Range(min=1)]),
            Int('tail_lines', default=500, validators=[Range(min=1)], null=True),
            Str('pod_name', required=True, empty=False),
            Str('container_name', required=True, empty=False),
        )
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

    @accepts()
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
            'certificate.query', [['revoked', '=', False], ['cert_type_CSR', '=', False], ['parsed', '=', True]]
        )

    @accepts()
    @returns(List(items=[Ref('certificateauthority_entry')]))
    async def certificate_authority_choices(self):
        """
        Returns certificate authorities which can be used by applications.
        """
        return await self.middleware.call(
            'certificateauthority.query', [['revoked', '=', False], ['parsed', '=', True]]
        )

    @private
    async def retrieve_pv_pvc_mapping(self, release_name):
        chart_release = await self.middleware.call(
            'chart.release.query', [['id', '=', release_name]], {'get': True, 'extra': {'retrieve_resources': True}}
        )
        return await self.retrieve_pv_pvc_mapping_internal(chart_release)

    @private
    async def retrieve_pv_pvc_mapping_internal(self, chart_release):
        mapping = {}
        release_vol_ds = os.path.join(chart_release['dataset'], 'volumes')
        zfs_volumes = {
            zv['metadata']['name']: zv for zv in await self.middleware.call(
                'k8s.zv.query', [['spec.poolName', '=', release_vol_ds]]
            )
        }

        for pv in chart_release['resources']['persistent_volumes']:
            claim_name = pv['spec'].get('claim_ref', {}).get('name')
            if claim_name:
                csi_spec = pv['spec']['csi']
                volumes_ds = csi_spec['volume_attributes']['openebs.io/poolname']
                if (
                    os.path.join(chart_release['dataset'], 'volumes') != volumes_ds or
                    csi_spec['volume_handle'] not in zfs_volumes
                ):
                    # We are only going to backup/restore pvc's which were consuming
                    # their respective storage class and we have related zfs volume present
                    continue

                pv_name = pv['metadata']['name']
                mapping[claim_name] = {
                    'name': pv_name,
                    'pv_details': pv,
                    'dataset': os.path.join(volumes_ds, csi_spec['volume_handle']),
                    'zv_details': zfs_volumes[csi_spec['volume_handle']],
                }
        return mapping

    @private
    async def create_update_storage_class_for_chart_release(self, release_name, volumes_path):
        storage_class_name = get_storage_class_name(release_name)
        storage_class = await self.middleware.call('k8s.storage_class.retrieve_storage_class_manifest')
        storage_class['metadata']['name'] = storage_class_name
        storage_class['parameters']['poolname'] = volumes_path
        if await self.middleware.call('k8s.storage_class.query', [['metadata.name', '=', storage_class_name]]):
            await self.middleware.call('k8s.storage_class.update', storage_class_name, storage_class)
        else:
            await self.middleware.call('k8s.storage_class.create', storage_class)

    @private
    async def recreate_storage_class(self, release_name, volumes_path):
        storage_class_name = get_storage_class_name(release_name)
        if await self.middleware.call('k8s.storage_class.query', [['metadata.name', '=', storage_class_name]]):
            await self.middleware.call('k8s.storage_class.delete', storage_class_name)
        await self.create_update_storage_class_for_chart_release(release_name, volumes_path)

    @accepts(Str('release_name'))
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
                    'available': (r_data['status']['ready_replicas'] or 0),
                    'desired': (r_data['status']['replicas'] or 0),
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

    @private
    async def get_workload_storage_details(self):
        mapping = {
            'storage_classes': collections.defaultdict(lambda: None),
            'persistent_volumes': collections.defaultdict(list),
        }
        k8s_config = await self.middleware.call('kubernetes.config')
        if not k8s_config['dataset']:
            return mapping

        for storage_class in await self.middleware.call('k8s.storage_class.query'):
            mapping['storage_classes'][storage_class['metadata']['name']] = storage_class

        # If the chart release was consuming any PV's, they would have to be manually removed from k8s database
        # because of chart release reclaim policy being retain
        for pv in await self.middleware.call(
                'k8s.pv.query', [[
                    'spec.csi.volume_attributes.openebs\\.io/poolname', '^',
                    f'{os.path.join(k8s_config["dataset"], "releases")}/'
                ]]
        ):
            dataset = pv['spec']['csi']['volume_attributes']['openebs.io/poolname']
            rl = dataset.split('/', 4)
            if len(rl) > 4:
                mapping['persistent_volumes'][rl[3]].append(pv)

        return mapping

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
                    workload_status[release_name]['desired'] += (r_data['status']['replicas'] or 0)
                    workload_status[release_name]['available'] += (r_data['status']['ready_replicas'] or 0)

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
