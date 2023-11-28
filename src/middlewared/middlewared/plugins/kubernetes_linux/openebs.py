import itertools

from middlewared.schema import accepts, Dict, Str, ValidationErrors
from middlewared.service import CRUDService, filterable
from middlewared.utils import filter_list

from .k8s import ZFSSnapshot, ZFSVolume, ZFSVolumeSnapshot, ZFSVolumeSnapshotClass


class KubernetesZFSVolumesService(CRUDService):

    NAMESPACE = 'openebs'

    class Config:
        namespace = 'k8s.zv'
        private = True

    @filterable
    async def query(self, filters, options):
        return filter_list((await ZFSVolume.query())['items'], filters, options)

    @accepts(Str('volume_name'))
    async def do_delete(self, volume_name):
        return await ZFSVolume.delete(volume_name, namespace=self.NAMESPACE)


class KubernetesZFSSnapshotClassService(CRUDService):

    class Config:
        namespace = 'k8s.zfs.snapshotclass'
        private = True

    @filterable
    async def query(self, filters, options):
        return filter_list((await ZFSVolumeSnapshotClass.query())['items'], filters, options)


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
