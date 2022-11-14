import asyncio
import collections

from middlewared.schema import Dict, List, Str, returns
from middlewared.service import accepts, private, Service
from middlewared.utils.itertools import infinite_multiplier_generator

from .utils import get_chart_release_from_namespace, get_namespace, is_ix_namespace


EVENT_LOCKS = collections.defaultdict(asyncio.Lock)
LOCKS = collections.defaultdict(asyncio.Lock)


class ChartReleaseService(Service):

    CHART_RELEASES = {}

    class Config:
        namespace = 'chart.release'

    @accepts(Str('release_name'))
    @returns(List(
        'events', items=[Dict(
            'event',
            Dict(
                'involved_object',
                Str('kind'),
                Str('name'),
                Str('namespace'),
                additional_attrs=True,
                null=True,
            ),
            Dict(
                'metadata',
                Str('namespace', required=True),
                Str('uid', required=True),
                Str('name', required=True),
                additional_attrs=True,
            ),
            additional_attrs=True,
        )]
    ))
    async def events(self, release_name):
        """
        Returns kubernetes events for `release_name` Chart Release.
        """
        return await self.middleware.call(
            'k8s.event.query', [], {
                'extra': {
                    'namespace': get_namespace(release_name),
                    'timestamp': True,
                },
                'order_by': ['metadata.creation_timestamp'],
            }
        )

    @private
    async def refresh_events_state(self, chart_release_name=None):
        filters = [['id', '=', chart_release_name]] if chart_release_name else []
        for chart_release in await self.middleware.call('chart.release.query', filters):
            async with LOCKS[chart_release['name']]:
                ChartReleaseService.CHART_RELEASES[chart_release['name']] = {
                    'data': chart_release,
                    'poll': False,
                }

    @private
    async def remove_chart_release_from_events_state(self, chart_release_name):
        async with LOCKS[chart_release_name]:
            ChartReleaseService.CHART_RELEASES.pop(chart_release_name, None)

    @private
    async def clear_cached_chart_releases(self):
        for name in list(self.CHART_RELEASES):
            await self.remove_chart_release_from_events_state(name)

    @private
    async def handle_k8s_event(self, k8s_event):
        name = get_chart_release_from_namespace(k8s_event['involvedObject']['namespace'])
        async with EVENT_LOCKS[name]:
            if name not in self.CHART_RELEASES:
                # It's possible the chart release got deleted
                return

            async with LOCKS[name]:
                status = await self.middleware.call('chart.release.pod_status', name)
                cached_chart_release = self.CHART_RELEASES[name]
                if status['status'] != 'DEPLOYING':
                    cached_chart_release['poll'] = False
                    await self.changed_status_event(name, status, cached_chart_release)
                elif not cached_chart_release['poll']:
                    cached_chart_release['poll'] = True
                    asyncio.ensure_future(self.poll_chart_release_status(name))

    @private
    async def changed_status_event(self, name, new_status, cached_chart_release):
        if new_status['status'] != cached_chart_release['data']['status']:
            cached_chart_release['data'].update({
                'status': new_status['status'],
                'pod_status': {
                    'desired': new_status['desired'],
                    'available': new_status['available'],
                }
            })
            self.middleware.send_event(
                'chart.release.query', 'CHANGED', id=name, fields=cached_chart_release['data']
            )

    @private
    async def poll_chart_release_status(self, name):
        for sleep_sec in infinite_multiplier_generator(2, 1024, 2):
            async with LOCKS[name]:
                release_data = self.CHART_RELEASES.get(name)
                if not release_data or not release_data['poll']:
                    break
                status = await self.middleware.call('chart.release.pod_status', name)
                await self.changed_status_event(name, status, release_data)
                if status['status'] != 'DEPLOYING':
                    release_data['poll'] = False
                    break

            await asyncio.sleep(sleep_sec)


async def chart_release_event(middleware, event_type, args):
    args = args['fields']
    if args['involvedObject']['kind'] != 'Pod' or not is_ix_namespace(args['involvedObject']['namespace']):
        return

    await middleware.call('chart.release.handle_k8s_event', args)


async def setup(middleware):
    middleware.event_subscribe('kubernetes.events', chart_release_event)
    if await middleware.call('kubernetes.validate_k8s_setup', False):
        asyncio.ensure_future(middleware.call('chart.release.refresh_events_state'))
