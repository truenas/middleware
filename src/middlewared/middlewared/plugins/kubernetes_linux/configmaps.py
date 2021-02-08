from middlewared.service import CRUDService, filterable
from middlewared.utils import filter_list

from .k8s import api_client


class KubernetesSecretService(CRUDService):

    class Config:
        namespace = 'k8s.configmap'
        private = True

    @filterable
    async def query(self, filters, options):
        options = options or {}
        label_selector = options.get('extra', {}).get('label_selector')
        kwargs = {k: v for k, v in [('label_selector', label_selector)] if v}
        async with api_client() as (api, context):
            return filter_list(
                [d.to_dict() for d in (await context['core_api'].list_config_map_for_all_namespaces(**kwargs)).items],
                filters, options
            )
