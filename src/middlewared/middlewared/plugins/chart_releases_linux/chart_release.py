import collections
import copy
import errno
import itertools
import os
import shutil
import textwrap

from pkg_resources import parse_version

from middlewared.schema import accepts, Bool, Dict, Int, List, Str
from middlewared.service import CallError, CRUDService, filterable, job, private
from middlewared.utils import filter_list
from middlewared.validators import Match

from .utils import (
    add_context_to_configuration, CHART_NAMESPACE_PREFIX, CONTEXT_KEY_NAME, get_action_context,
    get_namespace, get_storage_class_name, Resources, run,
)


class ChartReleaseService(CRUDService):

    class Config:
        datastore_primary_key_type = 'string'
        namespace = 'chart.release'
        cli_namespace = 'app.chart_release'

    ENTRY = Dict(
        'chart_release_entry',
        Str('name', required=True),
        Dict('info', additional_attrs=True),
        Dict('config', additional_attrs=True),
        List('hooks'),
        Int('version', required=True, description='Version of chart release'),
        Str('namespace', required=True),
        Dict(
            'chart_metadata',
            Str('name', required=True, description='Name of application'),
            Str('version', required=True, description='Version of application'),
            Str('latest_chart_version', required=True, description='Latest available version of application'),
            additional_attrs=True,
        ),
        Str('id', required=True),
        Str('catalog', required=True),
        Str('catalog_train', required=True),
        Str('path', required=True),
        Str('dataset', required=True),
        Str('status', required=True),
        List('used_ports', items=[
            Dict(
                'port',
                Int('port', required=True),
                Str('protocol', required=True),
            )
        ], required=True),
        Dict(
            'pod_status',
            Int('available', required=True),
            Int('desired', required=True),
            required=True,
        ),
        Bool('update_available', required=True),
        Str('human_version', required=True, description='Human friendly version identifier for chart release'),
        Str(
            'human_latest_version', required=True,
            description='Human friendly latest available version identifier for chart release'
        ),
        Bool(
            'container_images_update_available', required=True,
            description='Will be set when any image(s) being used in the chart release has a newer version available'
        ),
        Dict('portals', additional_attrs=True),
        Dict('chart_schema', null=True, additional_attrs=True),
        Dict('history', additional_attrs=True),
        Dict(
            'resources',
            Dict('storage_class', additional_attrs=True),
            List('persistent_volumes'),
            List('host_path_volumes'),
            List('locked_host_paths'),
            Dict('container_images', additional_attrs=True),
            List('truenas_certificates', items=[Int('certificate_id')]),
            List('truenas_certificate_authorities', items=[Int('certificate_authority_id')]),
            *[List(r.value) for r in Resources],
        ),
    )

    @filterable
    async def query(self, filters, options):
        """
        Query available chart releases.

        `query-options.extra.retrieve_resources` is a boolean when set will retrieve existing kubernetes resources
        in the chart namespace.

        `query-options.extra.history` is a boolean when set will retrieve all chart version upgrades
        for a chart release.

        `query-options.extra.include_chart_schema` is a boolean when set will retrieve the schema being used by
        the chart release in question.

        `query-options.extra.resource_events` is a boolean when set will retrieve individual events of each resource.
        This only has effect if `query-options.extra.retrieve_resources` is set.
        """
        if not await self.middleware.call('kubernetes.validate_k8s_setup', False):
            # We use filter_list here to ensure that `options` are respected, options like get: true
            return filter_list([], filters, options)

        k8s_config = await self.middleware.call('kubernetes.config')
        update_catalog_config = {}
        catalogs = await self.middleware.call('catalog.query', [], {'extra': {'item_details': True}})
        container_images = {}
        for image in await self.middleware.call('container.image.query'):
            for tag in image['repo_tags']:
                if not container_images.get(tag):
                    container_images[tag] = image

        for catalog in catalogs:
            update_catalog_config[catalog['label']] = {}
            for train in catalog['trains']:
                train_data = {}
                for catalog_item in catalog['trains'][train]:
                    max_version = catalog['trains'][train][catalog_item]['latest_version'] or '0.0.0'
                    app_version = catalog['trains'][train][catalog_item]['latest_app_version'] or '0.0.0'
                    train_data[catalog_item] = {
                        'chart_version': parse_version(max_version),
                        'app_version': app_version,
                    }

                update_catalog_config[catalog['label']][train] = train_data

        k8s_node_ip = await self.middleware.call('kubernetes.node_ip')
        options = options or {}
        extra = copy.deepcopy(options.get('extra', {}))
        retrieve_schema = extra.get('include_chart_schema')
        get_resources = extra.get('retrieve_resources')
        get_locked_paths = extra.get('retrieve_locked_paths')
        locked_datasets = await self.middleware.call('zfs.dataset.locked_datasets') if get_locked_paths else []
        get_history = extra.get('history')
        if retrieve_schema:
            questions_context = await self.middleware.call('catalog.get_normalised_questions_context')
        else:
            questions_context = None

        if filters and len(filters) == 1 and filters[0][:2] == ['id', '=']:
            extra['namespace_filter'] = ['metadata.namespace', '=', f'{CHART_NAMESPACE_PREFIX}{filters[0][-1]}']
            resources_filters = [extra['namespace_filter']]
        else:
            resources_filters = [['metadata.namespace', '^', CHART_NAMESPACE_PREFIX]]

        ports_used = collections.defaultdict(list)
        service_filters = [['spec.type', '=', 'LoadBalancer']] if k8s_config['servicelb'] else []
        for k8s_svc in await self.middleware.call(
            'k8s.service.query', [['OR', [['spec.type', '=', 'NodePort']] + service_filters]] + resources_filters
        ):
            release_name = k8s_svc['metadata']['namespace'][len(CHART_NAMESPACE_PREFIX):]
            ports_used[release_name].extend([
                {
                    'port': p['port' if k8s_svc['spec']['type'] == 'LoadBalancer' else 'nodePort'],
                    'protocol': p['protocol']
                }
                for p in k8s_svc['spec']['ports']
            ])

        if get_resources:
            storage_mapping = await self.middleware.call('chart.release.get_workload_storage_details')

        resources_mapping = await self.middleware.call('chart.release.get_resources_with_workload_mapping', {
            'resource_events': extra.get('resource_events', False),
            'resource_filters': resources_filters,
            'resources': [
                r.name for r in (
                    Resources if get_resources else [Resources.POD, Resources.DEPLOYMENT, Resources.STATEFULSET]
                )
            ],
        })
        resources = resources_mapping['resources']

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

            pods_status = resources_mapping['workload_status'][name]
            pod_diff = pods_status['available'] - pods_status['desired']
            status = 'ACTIVE'
            if pod_diff == 0 and pods_status['desired'] == 0:
                status = 'STOPPED'
            elif pod_diff < 0:
                status = 'DEPLOYING'

            # We will retrieve all host ports being used
            for pod in filter(lambda p: p['status']['phase'] == 'Running', resources[Resources.POD.value][name]):
                for container in pod['spec']['containers']:
                    ports_used[name].extend([
                        {'port': p['hostPort'], 'protocol': p['protocol']}
                        for p in (container['ports'] or []) if p['hostPort']
                    ])

            release_data.update({
                'path': os.path.join('/mnt', k8s_config['dataset'], 'releases', name),
                'dataset': os.path.join(k8s_config['dataset'], 'releases', name),
                'config': config,
                'status': status,
                'used_ports': ports_used[name],
                'pod_status': pods_status,
            })

            container_images_normalized = {
                i_name: {
                    'id': image_details.get('id'),
                    'update_available': image_details.get('update_available', False)
                } for i_name, image_details in map(
                    lambda i: (i, container_images.get(i, {})),
                    list(set(
                        c['image']
                        for workload_type in ('deployments', 'statefulsets')
                        for workload in resources[workload_type][name]
                        for c in workload['spec']['template']['spec']['containers']
                    ))
                )
            }
            if get_resources:
                release_resources = {
                    'storage_class': storage_mapping['storage_classes'][get_storage_class_name(name)],
                    'persistent_volumes': storage_mapping['persistent_volumes'][name],
                    'host_path_volumes': await self.host_path_volumes(itertools.chain(
                        *[resources[getattr(Resources, k).value][name] for k in ('DEPLOYMENT', 'STATEFULSET')]
                    )),
                    **{r.value: resources[r.value][name] for r in Resources},
                    'container_images': container_images_normalized,
                    'truenas_certificates': [v['id'] for v in
                                             release_data['config'].get('ixCertificates', {}).values()],
                    'truenas_certificate_authorities': [
                        v['id'] for v in release_data['config'].get('ixCertificateAuthorities', {}).values()
                    ],
                }
                if get_locked_paths:
                    release_resources['locked_host_paths'] = [
                        v for v in release_resources['host_path_volumes']
                        if await self.middleware.call('pool.dataset.path_in_locked_datasets', v, locked_datasets)
                    ]

                release_data['resources'] = release_resources

            if get_history:
                release_data['history'] = release['history']
                for k, v in release_data['history'].items():
                    r_app_version = self.normalize_app_version_of_chart_release(v)
                    release_data['history'][k].update({
                        'human_version': f'{r_app_version}_{parse_version(v["chart_metadata"]["version"])}',
                    })

            current_version = parse_version(release_data['chart_metadata']['version'])
            catalog_version_dict = update_catalog_config.get(release_data['catalog'], {}).get(
                release_data['catalog_train'], {}
            ).get(release_data['chart_metadata']['name'], {})
            latest_version = catalog_version_dict.get('chart_version', current_version)
            latest_app_version = catalog_version_dict.get('app_version')
            release_data['update_available'] = latest_version > current_version

            app_version = self.normalize_app_version_of_chart_release(release_data)
            if release_data['chart_metadata']['name'] == 'ix-chart':
                # Latest app version for ix-chart remains same
                latest_app_version = app_version

            for key, app_v, c_v in (
                ('human_version', app_version, current_version),
                ('human_latest_version', latest_app_version, latest_version),
            ):
                if app_v:
                    release_data[key] = f'{app_v}_{c_v}'
                else:
                    release_data[key] = str(c_v)

            if retrieve_schema:
                chart_path = os.path.join(release_data['path'], 'charts', release_data['chart_metadata']['version'])
                if os.path.exists(chart_path):
                    release_data['chart_schema'] = await self.middleware.call(
                        'catalog.item_version_details', chart_path, questions_context
                    )
                else:
                    release_data['chart_schema'] = None

            release_data['container_images_update_available'] = any(
                details['update_available'] for details in container_images_normalized.values()
            )
            release_data['chart_metadata']['latest_chart_version'] = str(latest_version)
            release_data['portals'] = await self.middleware.call(
                'chart.release.retrieve_portals_for_chart_release', release_data, k8s_node_ip
            )

            if 'icon' not in release_data['chart_metadata']:
                release_data['chart_metadata']['icon'] = None

            releases.append(release_data)

        return filter_list(releases, filters, options)

    @private
    def normalize_app_version_of_chart_release(self, release_data):
        app_version = None
        if release_data['chart_metadata']['name'] == 'ix-chart':
            image_config = release_data['config'].get('image') or {}
            if all(k in image_config for k in ('tag', 'repository')):
                # TODO: Let's see if we can find sane versioning for `latest` from upstream
                if image_config['tag'] == 'latest':
                    app_version = f'{image_config["repository"]}:{image_config["tag"]}'
                else:
                    app_version = image_config['tag']
        else:
            app_version = release_data['chart_metadata'].get('appVersion')
        return app_version

    @private
    async def host_path_volumes(self, resources):
        host_path_volumes = []
        for resource in resources:
            for volume in filter(
                lambda v: (v.get('host_path') or {}).get('path'), resource['spec']['template']['spec']['volumes'] or []
            ):
                host_path_volumes.append(volume['host_path']['path'])
        return host_path_volumes

    @private
    async def normalise_and_validate_values(self, item_details, values, update, release_ds, release_data=None):
        dict_obj = await self.middleware.call(
            'chart.release.validate_values', item_details, values, update, release_data,
        )
        return await self.middleware.call(
            'chart.release.get_normalised_values', dict_obj, values, update, {
                'release': {
                    'name': release_ds.split('/')[-1],
                    'dataset': release_ds,
                    'path': os.path.join('/mnt', release_ds),
                },
                'actions': [],
            }
        )

    @private
    async def perform_actions(self, context):
        for action in context['actions']:
            await self.middleware.call(f'chart.release.{action["method"]}', *action['args'])

    @accepts(
        Dict(
            'chart_release_create',
            Dict('values', additional_attrs=True),
            Str('catalog', required=True),
            Str('item', required=True),
            Str(
                'release_name', required=True, validators=[Match(
                    r'^[a-z]([-a-z0-9]*[a-z0-9])?$',
                    explanation=textwrap.dedent(
                        '''
                        Application name must have the following:
                        1) Lowercase alphanumeric characters can be specified
                        2) Name must start with an alphabetic character and can end with alphanumeric character
                        3) Hyphen '-' is allowed but not as the first or last character
                        e.g abc123, abc, abcd-1232
                        '''
                    )
                )]
            ),
            Str('train', default='charts'),
            Str('version', default='latest'),
        )
    )
    @job(lock=lambda args: f'chart_release_create_{args[0]["release_name"]}')
    async def do_create(self, job, data):
        """
        Create a chart release for a catalog item.

        `release_name` is the name which will be used to identify the created chart release.

        `catalog` is a valid catalog id where system will look for catalog `item` details.

        `train` is which train to look for under `catalog` i.e stable / testing etc.

        `version` specifies the catalog `item` version.

        `values` is configuration specified for the catalog item version in question which will be used to
        create the chart release.
        """
        await self.middleware.call('kubernetes.validate_k8s_setup')
        if await self.query([['id', '=', data['release_name']]]):
            raise CallError(f'Chart release with {data["release_name"]} already exists.', errno=errno.EEXIST)

        catalog = await self.middleware.call('catalog.get_instance', data['catalog'])
        item_details = await self.middleware.call('catalog.get_item_details', data['item'], {
            'catalog': data['catalog'],
            'train': data['train'],
        })
        version = data['version']
        if version == 'latest':
            version = await self.middleware.call(
                'chart.release.get_latest_version_from_item_versions', item_details['versions']
            )

        if version not in item_details['versions']:
            raise CallError(f'Unable to locate "{data["version"]}" catalog item version.', errno=errno.ENOENT)

        item_details = item_details['versions'][version]
        await self.middleware.call('catalog.version_supported_error_check', item_details)

        k8s_config = await self.middleware.call('kubernetes.config')
        release_ds = os.path.join(k8s_config['dataset'], 'releases', data['release_name'])
        # The idea is to validate the values provided first and if it passes our validation test, we
        # can move forward with setting up the datasets and installing the catalog item
        new_values = data['values']
        new_values, context = await self.normalise_and_validate_values(item_details, new_values, False, release_ds)

        job.set_progress(25, 'Initial Validation completed')

        # Now that we have completed validation for the item in question wrt values provided,
        # we will now perform the following steps
        # 1) Create release datasets
        # 2) Copy chart version into release/charts dataset
        # 3) Install the helm chart
        # 4) Create storage class
        try:
            job.set_progress(30, 'Creating chart release datasets')

            for dataset in await self.release_datasets(release_ds):
                if not await self.middleware.call('zfs.dataset.query', [['id', '=', dataset]]):
                    await self.middleware.call('zfs.dataset.create', {'name': dataset, 'type': 'FILESYSTEM'})
                    await self.middleware.call('zfs.dataset.mount', dataset)

            job.set_progress(45, 'Created chart release datasets')

            chart_path = os.path.join('/mnt', release_ds, 'charts', version)
            await self.middleware.run_in_thread(lambda: shutil.copytree(item_details['location'], chart_path))

            job.set_progress(55, 'Completed setting up chart release')
            # Before finally installing the release, we will perform any actions which might be required
            # for the release to function like creating/deleting ix-volumes
            await self.perform_actions(context)

            namespace_name = get_namespace(data['release_name'])

            job.set_progress(65, f'Creating {namespace_name} for chart release')
            namespace_body = {
                'metadata': {
                    'labels': {
                        'catalog': data['catalog'],
                        'catalog_train': data['train'],
                        'catalog_branch': catalog['branch'],
                    },
                    'name': namespace_name,
                }
            }
            if not await self.middleware.call('k8s.namespace.query', [['metadata.name', '=', namespace_name]]):
                await self.middleware.call('k8s.namespace.create', {'body': namespace_body})
            else:
                await self.middleware.call('k8s.namespace.update', namespace_name, {'body': namespace_body})

            job.set_progress(75, 'Installing Catalog Item')

            new_values = await add_context_to_configuration(new_values, {
                CONTEXT_KEY_NAME: {
                    **get_action_context(data['release_name']),
                    'operation': 'INSTALL',
                    'isInstall': True,
                }
            }, self.middleware)

            await self.middleware.call(
                'chart.release.create_update_storage_class_for_chart_release',
                data['release_name'], os.path.join(release_ds, 'volumes')
            )

            # We will install the chart now and force the installation in an ix based namespace
            # https://github.com/helm/helm/issues/5465#issuecomment-473942223
            await self.middleware.call(
                'chart.release.helm_action', data['release_name'], chart_path, new_values, 'install'
            )
        except Exception:
            job.set_progress(80, f'Failure occurred while installing {data["release_name"]!r}, cleaning up')
            # Do a rollback here
            # Let's uninstall the release as well if it did get installed ( it is possible this might have happened )
            if await self.middleware.call('chart.release.query', [['id', '=', data['release_name']]]):
                delete_job = await self.middleware.call('chart.release.delete', data['release_name'])
                await delete_job.wait()
                if delete_job.error:
                    self.logger.error('Failed to uninstall helm chart release: %s', delete_job.error)
            else:
                await self.post_remove_tasks(data['release_name'], job)

            raise
        else:
            await self.middleware.call('chart.release.refresh_events_state', data['release_name'])
            job.set_progress(100, 'Chart release created')
            return await self.get_instance(data['release_name'])

    @accepts(
        Str('chart_release'),
        Dict(
            'chart_release_update',
            Dict('values', additional_attrs=True),
        )
    )
    @job(lock=lambda args: f'chart_release_update_{args[0]}')
    async def do_update(self, job, chart_release, data):
        """
        Update an existing chart release.

        `values` is configuration specified for the catalog item version in question which will be used to
        create the chart release.
        """
        release = await self.get_instance(chart_release)
        release_orig = copy.deepcopy(release)
        chart_path = os.path.join(release['path'], 'charts', release['chart_metadata']['version'])
        if not os.path.exists(chart_path):
            raise CallError(
                f'Unable to locate {chart_path!r} chart version for updating {chart_release!r} chart release',
                errno=errno.ENOENT
            )

        version_details = await self.middleware.call('catalog.item_version_details', chart_path)
        config = release['config']
        config.update(data['values'])
        # We use update=False because we want defaults to be populated again if they are not present in the payload
        # Why this is not dangerous is because the defaults will be added only if they are not present/configured for
        # the chart release.
        config, context = await self.normalise_and_validate_values(
            version_details, config, False, release['dataset'], release_orig,
        )

        job.set_progress(25, 'Initial Validation complete')

        await self.perform_actions(context)

        config = await add_context_to_configuration(config, {
            CONTEXT_KEY_NAME: {
                **get_action_context(chart_release),
                'operation': 'UPDATE',
                'isUpdate': True,
            }
        }, self.middleware)

        await self.middleware.call('chart.release.helm_action', chart_release, chart_path, config, 'update')

        if release_orig['status'] == 'STOPPED':
            await self.middleware.call('chart.release.scale', chart_release, {'replica_count': 0})

        job.set_progress(90, 'Syncing secrets for chart release')
        await self.middleware.call('chart.release.sync_secrets_for_release', chart_release)
        await self.middleware.call('chart.release.refresh_events_state', chart_release)

        job.set_progress(100, 'Update completed for chart release')
        return await self.get_instance(chart_release)

    @accepts(
        Str('release_name'),
        Dict(
            'options',
            Bool('delete_unused_images', default=False),
        )
    )
    @job(lock=lambda args: f'chart_release_delete_{args[0]}')
    async def do_delete(self, job, release_name, options):
        """
        Delete existing chart release.

        This will delete the chart release from the kubernetes cluster and also remove any associated volumes / data.
        To clarify, host path volumes will not be deleted which live outside the chart release dataset.
        """
        # For delete we will uninstall the release first and then remove the associated datasets
        await self.middleware.call('kubernetes.validate_k8s_setup')
        chart_release = await self.get_instance(release_name, {'extra': {'retrieve_resources': True}})
        namespace = get_namespace(release_name)

        cp = await run(['helm', 'uninstall', release_name, '-n', namespace], check=False)
        if cp.returncode:
            raise CallError(f'Unable to uninstall "{release_name}" chart release: {cp.stderr}')

        job.set_progress(50, f'Uninstalled {release_name}')

        # It's possible pre-install jobs failed and in that case the jobs would not be cleaned up
        pre_install_jobs = [
            pre_install_job['metadata']['name']
            for pre_install_job in await self.middleware.call(
                'k8s.job.query', [
                    ['metadata.namespace', '=', namespace],
                    ['metadata.annotations', 'rin', 'helm.sh/hook'],
                ]
            )
        ]
        for pre_install_job_name in pre_install_jobs:
            await self.middleware.call('k8s.job.delete', pre_install_job_name, {'namespace': namespace})

        if pre_install_jobs:
            job.set_progress(60, 'Deleted pre-install jobs')
            # If we had pre-install jobs, it's possible we have leftover pods which the job did not remove
            # based on dev specified settings of cleaning it up - let's remove those
            for pod in await self.middleware.call('k8s.pod.query', [['metadata.namespace', '=', namespace]]):
                owner_references = pod['metadata'].get('owner_references')
                if not isinstance(owner_references, list) or all(
                    owner_reference.get('name') not in pre_install_jobs for owner_reference in owner_references
                ):
                    continue

                await self.middleware.call('k8s.pod.delete', pod['metadata']['name'], {'namespace': namespace})

        job.set_progress(75, f'Waiting for {release_name!r} pods to terminate')
        await self.middleware.call('chart.release.wait_for_pods_to_terminate', get_namespace(release_name))

        await self.post_remove_tasks(release_name, job)

        await self.middleware.call('chart.release.remove_chart_release_from_events_state', release_name)
        await self.middleware.call('chart.release.clear_chart_release_portal_cache', release_name)
        await self.middleware.call('alert.oneshot_delete', 'ChartReleaseUpdate', release_name)
        if options['delete_unused_images']:
            job.set_progress(97, 'Deleting unused container images')
            failed = await self.middleware.call('chart.release.delete_unused_app_images', chart_release)
            if failed:
                msg = '\n'
                for i, v in failed.items():
                    msg += f'{i+1}) {v[0]} ({v[1]})\n'
                raise CallError(f'{release_name!r} was deleted but unable to delete following images:{msg}')

        job.set_progress(100, f'{release_name!r} chart release deleted')
        return True

    @private
    async def post_remove_tasks(self, release_name, job=None):
        await self.remove_storage_class_and_dataset(release_name, job)
        await self.middleware.call('k8s.namespace.delete', get_namespace(release_name))

    @private
    async def remove_storage_class_and_dataset(self, release_name, job=None):
        storage_class_name = get_storage_class_name(release_name)
        if await self.middleware.call('k8s.storage_class.query', [['metadata.name', '=', storage_class_name]]):
            if job:
                job.set_progress(85, f'Removing {release_name!r} storage class')
            try:
                await self.middleware.call('k8s.storage_class.delete', storage_class_name)
            except Exception as e:
                self.logger.error('Failed to remove %r storage class: %s', storage_class_name, e)

        k8s_config = await self.middleware.call('kubernetes.config')
        release_ds = os.path.join(k8s_config['dataset'], 'releases', release_name)

        # If the chart release was consuming any PV's, they would have to be manually removed from k8s database
        # because of chart release reclaim policy being retain
        pvc_volume_ds = os.path.join(release_ds, 'volumes')
        for pv in await self.middleware.call(
            'k8s.pv.query', [
                ['spec.csi.volume_attributes.openebs\\.io/poolname', '=', pvc_volume_ds]
            ]
        ):
            await self.middleware.call('k8s.pv.delete', pv['metadata']['name'])

        failed_zfs_volumes = []
        # We would like to delete openebs zfs volumes ( not actual zfs volumes ) in openebs namespace
        for zfs_volume in await self.middleware.call('k8s.zv.query', [['spec.poolName', '=', pvc_volume_ds]]):
            try:
                await self.middleware.call('k8s.zv.delete', zfs_volume['metadata']['name'])
            except Exception:
                # It's perfectly fine if this fails as functionality wise this change is just cosmetic
                # and is essentially cleaning up leftover zfs volume entries from k8s db
                failed_zfs_volumes.append(zfs_volume['metadata']['name'])

        if failed_zfs_volumes:
            self.logger.error(
                'Failed to delete %r zfs volumes when deleting %r chart release',
                ', '.join(failed_zfs_volumes), release_name
            )

        if await self.middleware.call('zfs.dataset.query', [['id', '=', release_ds]]):
            if job:
                job.set_progress(95, f'Removing {release_ds!r} dataset')
            await self.middleware.call('zfs.dataset.delete', release_ds, {'recursive': True, 'force': True})

    @private
    async def release_datasets(self, release_dataset):
        return [release_dataset] + [
            os.path.join(release_dataset, k) for k in ('charts', 'volumes', 'volumes/ix_volumes')
        ]

    @private
    async def get_chart_namespace_prefix(self):
        return CHART_NAMESPACE_PREFIX
