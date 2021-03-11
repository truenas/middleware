from middlewared.service import CRUDService, filterable
from middlewared.utils import filter_list

from .k8s import api_client


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
