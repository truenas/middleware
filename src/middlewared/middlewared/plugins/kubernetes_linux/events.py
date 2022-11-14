import asyncio

from aiohttp import client_exceptions
from datetime import datetime
from dateutil.parser import parse as datetime_parse
from dateutil.tz import tzutc

from middlewared.service import CRUDService

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
        start_time = datetime.now(tz=tzutc())
        async for event in Event.stream():
            event_obj = event['object']
            check_time = datetime_parse(
                event_obj['eventTime'] or event_obj['lastTimestamp'] or event_obj['firstTimestamp']
            )

            if not check_time or start_time > check_time or event['type'] != 'ADDED' or (
                event_obj['involvedObject']['uid'] != NODE_NAME and not event_obj['metadata']['namespace'].startswith(
                    chart_namespace_prefix
                )
            ):
                continue

            self.middleware.send_event(
                'kubernetes.events', 'ADDED', uid=event_obj['involvedObject']['uid'], fields=event_obj
            )


async def setup(middleware):
    middleware.event_register('kubernetes.events', 'Kubernetes cluster events')
    # We are going to check in setup k8s events if setting up events is relevant or not
    asyncio.ensure_future(middleware.call('k8s.event.setup_k8s_events'))
