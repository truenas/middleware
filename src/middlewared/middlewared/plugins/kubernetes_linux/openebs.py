import itertools
import os
import tempfile
import yaml

from middlewared.schema import accepts, Dict, Str, ValidationErrors
from middlewared.service import CallError, CRUDService, filterable
from middlewared.utils import filter_list, run

from .k8s_new import ZFSSnapshot, ZFSVolume, ZFSVolumeSnapshot, ZFSVolumeSnapshotClass
from .utils import NODE_NAME, KUBECONFIG_FILE


class KubernetesZFSVolumesService(CRUDService):

    NAMESPACE = 'openebs'

    class Config:
        namespace = 'k8s.zv'
        private = True

    @filterable
    async def query(self, filters, options):
        return filter_list((await ZFSVolume.query())['items'], filters, options)

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
            'apiVersion': f'zfs.openebs.io/{ZFSVolume.VERSION}',
        })
        with tempfile.NamedTemporaryFile(mode='w+') as f:
            f.write(yaml.dump(data))
            f.flush()
            cp = await run(['k3s', 'kubectl', 'apply', '-f', f.name], env=dict(os.environ, KUBECONFIG=KUBECONFIG_FILE))
            if cp.returncode:
                raise CallError(f'Failed to create ZFS Volume: {cp.stderr.decode()}')

        return await self.query([
            ['metadata.name', '=', data['metadata']['name']],
            ['metadata.namespace', '=', data['metadata']['namespace']],
        ], {'get': True})

    @accepts(Str('volume_name'))
    async def do_delete(self, volume_name):
        return await ZFSVolume.delete(volume_name, namespace=self.NAMESPACE)


class KubernetesZFSSnapshotClassService(CRUDService):

    DEFAULT_SNAPSHOT_CLASS_NAME = 'zfspv-default-snapshot-class'

    class Config:
        namespace = 'k8s.zfs.snapshotclass'
        private = True

    @filterable
    async def query(self, filters, options):
        return filter_list((await ZFSVolumeSnapshotClass.query())['items'], filters, options)

    async def do_create(self, data):
        data.update({
            'kind': 'VolumeSnapshotClass',
            'apiVersion': f'snapshot.storage.k8s.io/{ZFSVolumeSnapshotClass.VERSION}',
        })
        await ZFSVolumeSnapshotClass.create(data)
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

    class Config:
        namespace = 'k8s.volume.snapshot'
        private = True

    @filterable
    async def query(self, filters, options):
        return filter_list(
            list(itertools.chain(*[
                (await ZFSVolumeSnapshot.query(namespace=namespace))['items']
                for namespace in await self.middleware.call('k8s.namespace.namespace_names')
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
            'apiVersion': f'snapshot.storage.k8s.io/{ZFSVolumeSnapshot.VERSION}'
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

        await ZFSVolumeSnapshot.create(data, namespace=namespace)
        return data

    @accepts(
        Str('snapshot_name'),
        Dict(
            'zfs_snapshot_delete',
            Str('namespace', required=True),
        )
    )
    async def do_delete(self, snapshot_name, options):
        await ZFSVolumeSnapshot.delete(snapshot_name, **options)
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
        return filter_list((await ZFSSnapshot.query(namespace='openebs')), filters, options)
