import itertools

from middlewared.service import CRUDService, filterable
from middlewared.utils import filter_list

from .k8s import api_client
from .utils import OPENEBS_ZFS_GROUP_NAME


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


class KubernetesZFSSnapshotClassService(CRUDService):

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

    async def setup_default_snapshot_class(self):
        await self.middleware.call('k8s.zfs.snapshotclass.create', {
            'metadata': {
                'name': 'zfspv-default-snapshot-class',
                'annotations': {
                    'snapshot.storage.kubernetes.io/is-default-class': 'true'
                },
            },
            'driver': 'zfs.csi.openebs.io',
            'deletionPolicy': 'Delete',
        })


class KubernetesZFSSnapshotService(CRUDService):

    GROUP = 'snapshot.storage.k8s.io'
    PLURAL = 'volumesnapshots'
    VERSION = 'v1'

    class Config:
        namespace = 'k8s.zfs.snapshot'
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
