import asyncio

from aiohttp import client_exceptions
from datetime import datetime
from dateutil.tz import tzutc
from kubernetes_asyncio import watch

from middlewared.service import CRUDService

from .k8s import api_client
from .k8s_base_resources import KubernetesBaseResource
from .k8s_new import Event
from .utils import NODE_NAME


class KubernetesEventService(KubernetesBaseResource, CRUDService):

    KUBERNETES_RESOURCE = Event

    class Config:
        namespace = 'k8s.event'
        private = True

    async def setup_k8s_events(self):
        if not await self.middleware.call('kubernetes.validate_k8s_setup', False):
            return

        try:
            await self.k8s_events_internal()
        except client_exceptions.ClientPayloadError:
            if not await self.middleware.call('service.started', 'kubernetes'):
                # This is okay and happens when k8s is stopped
                return
            raise

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
    # We are going to check in setup k8s events if setting up events is relevant or not
    asyncio.ensure_future(middleware.call('k8s.event.setup_k8s_events'))
