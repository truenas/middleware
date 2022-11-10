from middlewared.schema import accepts, Dict, Str
from middlewared.service import CallError, CRUDService, filterable
from middlewared.utils import filter_list

from .k8s_new import ApiException, K8sClientBase


class KubernetesBaseResource(CRUDService):

    QUERY_EVENTS: bool = False
    QUERY_EVENTS_RESOURCE_NAME: str = NotImplementedError
    KUBERNETES_RESOURCE: K8sClientBase = NotImplementedError

    @filterable
    async def query(self, filters, options):
        options = options or {}
        extra = options.get('extra', {})
        kwargs = {
            k: v for k, v in [
                ('labelSelector', extra.get('labelSelector')), ('fieldSelector', extra.get('fieldSelector'))
            ] if v
        }
        if len(filters) == 1 and len(filters[0]) == 3 and list(filters[0])[:2] == ['metadata.namespace', '=']:
            kwargs['namespace'] = filters[0][2]

        resources = [
            d for d in (await self.KUBERNETES_RESOURCE.query(**kwargs))['items']
            if await self.conditional_filtering_in_query(d, options)
        ]
        if self.QUERY_EVENTS and self.QUERY_EVENTS_RESOURCE_NAME is not NotImplementedError and extra.get('events'):
            events = await self.middleware.call(
                'kubernetes.get_events_of_resource_type', self.QUERY_EVENTS_RESOURCE_NAME,
                [r['metadata']['uid'] for r in resources]
            )
            for resource in resources:
                resource['events'] = events[resource['metadata']['uid']]

        return filter_list(resources, filters, options)

    async def conditional_filtering_in_query(self, entry, options):
        return True

    @accepts(
        Dict(
            'k8s_resource_create',
            Str('namespace', required=True),
            Dict('body', additional_attrs=True, required=True),
            register=True
        )
    )
    async def do_create(self, data):
        try:
            await self.KUBERNETES_RESOURCE.create(data['body'], namespace=data['namespace'])
        except ApiException as e:
            raise CallError(f'Unable to create {self.KUBERNETES_RESOURCE.OBJECT_HUMAN_NAME}: {e}')

    @accepts(
        Str('name'),
        Dict(
            'k8s_resource_update',
            Str('namespace', required=True),
            Dict('body', additional_attrs=True, required=True),
            register=True
        )
    )
    async def do_update(self, name, data):
        try:
            await self.KUBERNETES_RESOURCE.update(name, data['body'], namespace=data['namespace'])
        except ApiException as e:
            raise CallError(f'Unable to update {self.KUBERNETES_RESOURCE.OBJECT_HUMAN_NAME}: {e}')

    @accepts(
        Str('name'),
        Dict(
            'k8s_resource_delete_options',
            Str('namespace', required=True),
        )
    )
    async def do_delete(self, name, options):
        try:
            await self.KUBERNETES_RESOURCE.delete(name, **options)
        except ApiException as e:
            raise CallError(f'Unable to delete {self.KUBERNETES_RESOURCE.OBJECT_HUMAN_NAME}: {e}')
        else:
            return True
