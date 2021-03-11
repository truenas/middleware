from middlewared.service import CRUDService, filterable
from middlewared.utils import filter_list

from .k8s import api_client
from .utils import OPENEBS_ZFS_GROUP_NAME


class KubernetesPersistentVolumesService(CRUDService):

    class Config:
        namespace = 'k8s.pv'
        private = True

    @filterable
    async def query(self, filters, options):
        async with api_client() as (api, context):
            return filter_list(
                [
                    d.to_dict() for d in (
                        await context['core_api'].list_persistent_volume()
                    ).items
                ],
                filters, options
            )


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
