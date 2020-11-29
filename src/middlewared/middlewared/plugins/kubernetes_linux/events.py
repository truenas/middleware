import asyncio

from aiohttp import client_exceptions
from datetime import datetime
from dateutil.tz import tzutc
from kubernetes_asyncio import watch

from middlewared.service import CRUDService, filterable, private
from middlewared.utils import filter_list

from .k8s import api_client
from .utils import NODE_NAME


class KubernetesEventService(CRUDService):

    class Config:
        namespace = 'k8s.event'
        private = True

    @filterable
    async def query(self, filters, options):
        options = options or {}
        label_selector = options.get('extra', {}).get('label_selector')
        field_selector = options.get('extra', {}).get('field_selector')
        namespace = options.get('extra', {}).get('namespace')
        kwargs = {
            k: v for k, v in [
                ('label_selector', label_selector),
                ('field_selector', field_selector),
                ('namespace', namespace),
            ] if v
        }
        async with api_client() as (api, context):
            if namespace:
                method = context['core_api'].list_namespaced_event
            else:
                method = context['core_api'].list_event_for_all_namespaces
            return filter_list(
                [d.to_dict() for d in (await method(**kwargs)).items],
                filters, options
            )

    @private
    async def setup_k8s_events(self):
        if not await self.middleware.call('service.started', 'kubernetes'):
            return

        try:
            await self.k8s_events_internal()
        except client_exceptions.ClientPayloadError:
            if not await self.middleware.call('service.started', 'kubernetes'):
                # This is okay and happens when k8s is stopped
                return
            raise

    @private
    async def k8s_events_internal(self):
        chart_namespace_prefix = await self.middleware.call('chart.release.get_chart_namespace_prefix')
        async with api_client() as (api, context):
            watch_obj = watch.Watch()
            start_time = datetime.now(tz=tzutc())
            async with watch_obj.stream(context['core_api'].list_event_for_all_namespaces) as stream:
                async for event in stream:
                    event_obj = event['object']
                    check_time = event_obj.event_time or event_obj.last_timestamp or event_obj.first_timestamp

                    if not check_time or start_time > check_time or event['type'] != 'ADDED' or (
                        event_obj.involved_object.uid != NODE_NAME and not event_obj.metadata.namespace.startswith(
                            chart_namespace_prefix
                        )
                    ):
                        continue

                    self.middleware.send_event(
                        'kubernetes.events', 'ADDED', uid=event_obj.involved_object.uid, fields=event_obj.to_dict()
                    )


async def setup(middleware):
    middleware.event_register('kubernetes.events', 'Kubernetes cluster events')
    if await middleware.call('service.started', 'kubernetes'):
        asyncio.ensure_future(middleware.call('k8s.event.setup_k8s_events'))
