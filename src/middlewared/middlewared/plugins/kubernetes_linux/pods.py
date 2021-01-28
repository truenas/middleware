from middlewared.service import CRUDService, filterable
from middlewared.utils import filter_list

from .k8s import api_client


class KubernetesPodService(CRUDService):

    class Config:
        namespace = 'k8s.pod'
        private = True

    @filterable
    async def query(self, filters, options):
        options = options or {}
        label_selector = options.get('extra', {}).get('label_selector')
        kwargs = {k: v for k, v in [('label_selector', label_selector)] if v}
        async with api_client() as (api, context):
            pods = [d.to_dict() for d in (await context['core_api'].list_pod_for_all_namespaces(**kwargs)).items]
            events = await self.middleware.call(
                'kubernetes.get_events_of_resource_type', 'Pod', [p['metadata']['uid'] for p in pods]
            )

            for pod in pods:
                pod['events'] = events[pod['metadata']['uid']]

        return filter_list(pods, filters, options)
