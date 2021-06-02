import itertools
import os
import tempfile
import yaml

from middlewared.schema import accepts, Dict, Str, ValidationErrors
from middlewared.service import CallError, CRUDService, filterable
from middlewared.utils import filter_list, run

from .k8s import api_client
from .utils import OPENEBS_ZFS_GROUP_NAME, NODE_NAME, KUBECONFIG_FILE


class KubernetesZFSVolumesService(CRUDService):

    PLURAL = 'zfsvolumes'
    VERSION = 'v1'

    class Config:
        namespace = 'k8s.zv'
        private = True

    @filterable
    async def query(self, filters, options):
        async with api_client() as (api, context):
            return filter_list(
                [
                    d for d in (
                        await context['custom_object_api'].list_cluster_custom_object(
                            group=OPENEBS_ZFS_GROUP_NAME, version=self.VERSION, plural=self.PLURAL
                        )
                    )['items']
                ],
                filters, options
            )

    @accepts(
        Dict(
            'zfsvolume_create',
            Dict(
                'metadata',
                Str('name', required=True),
                Str('namespace', default='openebs'),
                additional_attrs=True,
            ),
            Dict(
                'spec',
                Str('capacity', required=True),
                Str('fsType', default='zfs'),
                Str('ownerNodeID', default=NODE_NAME),
                Str('poolName', required=True),
                Str('shared', default='yes'),
                Str('volumeType', default='DATASET'),
            ),
        )
    )
    async def do_create(self, data):
        # FIXME: API Client is not working - let's please change this to create ZV via api client
        data.update({
            'kind': 'ZFSVolume',
            'apiVersion': f'zfs.openebs.io/{self.VERSION}',
        })
        with tempfile.NamedTemporaryFile(mode='w+') as f:
            f.write(yaml.dump(data))
            f.flush()
            cp = await run(['k3s', 'kubectl', 'apply', '-f', f.name], env=dict(os.environ, KUBECONFIG=KUBECONFIG_FILE))
            if cp.returncode:
                raise CallError(f'Failed to create ZFS Volume: {cp.stderr.decode()}')

        return await self.query([
            ['metadata.name', '=', data['metadata']['name']],
            ['metadata.namespace', '=', data['namespace']],
        ], {'get': True})


class KubernetesZFSSnapshotClassService(CRUDService):

    DEFAULT_SNAPSHOT_CLASS_NAME = 'zfspv-default-snapshot-class'
    GROUP = 'snapshot.storage.k8s.io'
    PLURAL = 'volumesnapshotclasses'
    VERSION = 'v1'

    class Config:
        namespace = 'k8s.zfs.snapshotclass'
        private = True

    @filterable
    async def query(self, filters, options):
        async with api_client() as (api, context):
            return filter_list(
                [
                    d for d in (
                        await context['custom_object_api'].list_cluster_custom_object(
                            group=self.GROUP, version=self.VERSION, plural=self.PLURAL
                        )
                    )['items']
                ],
                filters, options
            )

    async def do_create(self, data):
        data.update({
            'kind': 'VolumeSnapshotClass',
            'apiVersion': f'snapshot.storage.k8s.io/{self.VERSION}',
        })
        async with api_client() as (api, context):
            await context['custom_object_api'].create_cluster_custom_object(
                group=self.GROUP, version=self.VERSION, plural=self.PLURAL, body=data
            )

        return data

    async def default_snapshot_class_name(self):
        return self.DEFAULT_SNAPSHOT_CLASS_NAME

    async def setup_default_snapshot_class(self):
        if await self.query([['metadata.name', '=', 'zfspv-default-snapshot-class']]):
            return

        await self.middleware.call('k8s.zfs.snapshotclass.create', {
            'metadata': {
                'name': self.DEFAULT_SNAPSHOT_CLASS_NAME,
                'annotations': {
                    'snapshot.storage.kubernetes.io/is-default-class': 'true'
                },
            },
            'driver': 'zfs.csi.openebs.io',
            'deletionPolicy': 'Delete',
        })


class KubernetesSnapshotService(CRUDService):

    GROUP = 'snapshot.storage.k8s.io'
    PLURAL = 'volumesnapshots'
    VERSION = 'v1'

    class Config:
        namespace = 'k8s.volume.snapshot'
        private = True

    @filterable
    async def query(self, filters, options):
        async with api_client() as (api, context):
            return filter_list(
                list(itertools.chain(*[
                    [
                        d for d in (
                            await context['custom_object_api'].list_namespaced_custom_object(
                                group=self.GROUP, version=self.VERSION, plural=self.PLURAL, namespace=namespace
                            )
                        )['items']
                    ] for namespace in await self.middleware.call('k8s.namespace.namespace_names')
                ])),
                filters, options
            )

    @accepts(
        Dict(
            'zfs_snapshot_create',
            Str('namespace', required=True),
            Dict(
                'metadata',
                Str('name', required=True),
                additional_attrs=True,
            ),
            Dict(
                'spec',
                Str('volumeSnapshotClassName', required=True),
                Dict(
                    'source',
                    Str('persistentVolumeClaimName', required=True),
                ),
                additional_attrs=True,
            ),
            additional_attrs=True,
        )
    )
    async def do_create(self, data):
        data.update({
            'kind': 'VolumeSnapshot',
            'apiVersion': f'snapshot.storage.k8s.io/{self.VERSION}'
        })
        namespace = data.pop('namespace')
        verrors = ValidationErrors()

        if not await self.middleware.call(
            'k8s.zfs.snapshotclass.query', [['metadata.name', '=', data['spec']['volumeSnapshotClassName']]]
        ):
            verrors.add(
                'zfs_snapshot_create.spec.volumeSnapshotClassName',
                'Specified volumeSnapshotClassName does not exist.'
            )

        if not await self.middleware.call(
            'k8s.pvc.query', [
                ['metadata.name', '=', data['spec']['source']['persistentVolumeClaimName']],
                ['metadata.namespace', '=', namespace]
            ]
        ):
            verrors.add(
                'zfs_snapshot_create.spec.source.persistentVolumeClaimName',
                f'Specified persistentVolumeClaimName does not exist in {namespace}.'
            )

        verrors.check()

        async with api_client() as (api, context):
            await context['custom_object_api'].create_namespaced_custom_object(
                group=self.GROUP, version=self.VERSION, plural=self.PLURAL, namespace=namespace, body=data
            )
        return data

    @accepts(
        Str('snapshot_name'),
        Dict(
            'zfs_snapshot_delete',
            Str('namespace', required=True),
        )
    )
    async def do_delete(self, snapshot_name, options):
        async with api_client() as (api, context):
            await context['custom_object_api'].delete_namespaced_custom_object(
                group=self.GROUP, version=self.VERSION, plural=self.PLURAL,
                namespace=options['namespace'], name=snapshot_name,
            )
        return True


class KubernetesZFSSnapshotService(CRUDService):

    GROUP = 'zfs.openebs.io'
    PLURAL = 'zfssnapshots'
    VERSION = 'v1'

    class Config:
        namespace = 'k8s.zfs.snapshot'
        private = True

    @filterable
    async def query(self, filters, options):
        async with api_client() as (api, context):
            return filter_list([
                d for d in (
                    await context['custom_object_api'].list_namespaced_custom_object(
                        group=self.GROUP, version=self.VERSION, plural=self.PLURAL, namespace='openebs'
                    )
                )['items']
            ], filters, options
            )
