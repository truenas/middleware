from middlewared.service import CRUDService, filterable
from middlewared.utils import filter_list

from .k8s import api_client


class KubernetesPodService(CRUDService):

    class Config:
        namespace = 'k8s.pod'
        private = True

    @filterable
    async def query(self, filters=None, options=None):
        options = options or {}
        label_selector = options.get('extra', {}).get('label_selector')
        kwargs = {k: v for k, v in [('label_selector', label_selector)] if v}
        async with api_client() as (api, context):
            return filter_list(
                [d.to_dict() for d in (await context['core_api'].list_pod_for_all_namespaces(**kwargs)).items],
                filters, options
            )
