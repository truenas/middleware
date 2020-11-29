from middlewared.service import CRUDService, filterable
from middlewared.utils import filter_list

from .k8s import api_client


class KubernetesPersistentVolumeClaimService(CRUDService):

    class Config:
        namespace = 'k8s.persistent_volume_claim'
        private = True

    @filterable
    async def query(self, filters, options):
        async with api_client() as (api, context):
            return filter_list(
                [
                    d.to_dict() for d in (
                        await context['core_api'].list_persistent_volume_claim_for_all_namespaces()
                    ).items
                ],
                filters, options
            )
