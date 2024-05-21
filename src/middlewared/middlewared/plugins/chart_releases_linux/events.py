import asyncio
import collections

from middlewared.event import EventSource
from middlewared.schema import Dict, Float, Int, List, Str, returns
from middlewared.service import accepts, private, Service
from middlewared.utils.itertools import infinite_multiplier_generator
from middlewared.validators import Range

from .utils import get_chart_release_from_namespace, get_namespace, is_ix_namespace


EVENT_LOCKS = collections.defaultdict(asyncio.Lock)
LOCKS = collections.defaultdict(asyncio.Lock)


class ChartReleaseStatsEventSource(EventSource):
    """
    Retrieve real time statistics for chart releases
    """
    ACCEPTS = Dict(
        Int('interval', default=2, validators=[Range(min_=2)]),
    )
    RETURNS = List(
        items=[Dict(
            'chart_release_stats',
            Str('id'),
            Dict(
                'stats',
                Int('memory', description='Memory usage of app in MB'),
                Float('cpu', description='Percentage of total core utilization'),
                Dict(
                    'network',
                    Int('incoming', description='All Incoming network traffic in bytes/sec'),
                    Int('outgoing', description='All Outgoing network traffic in bytes/sec'),
                )
            )
        )]
    )

    async def chart_stats(self, cached_stats):
        apps_info = await self.middleware.call(
            'chart.release.query', [], {'extra': {'stats': True}, 'select': ['id', 'stats']},
        )
        interval = self.arg['interval']

        for app_info in apps_info:
            if app_info['id'] not in cached_stats:
                cached_stats[app_info['id']] = {
                    'network_actual': app_info['stats']['network'],
                    'network_rate': {'incoming': 0, 'outgoing': 0}
                }
                app_info['stats']['network'] = {'incoming': 0, 'outgoing': 0}
            else:
                network_stats = app_info['stats']['network']
                cached_network_rate = cached_stats[app_info['id']]['network_rate']
                cached_network_stats = cached_stats[app_info['id']]['network_actual']
                cached_stats[app_info['id']] = {
                    'network_actual': app_info['stats']['network'],
                }
                app_info['stats']['network'] = {
                    'incoming': abs(network_stats['incoming'] - cached_network_stats['incoming']) / interval
                    or cached_network_rate['incoming'],
                    'outgoing': abs(network_stats['outgoing'] - cached_network_stats['outgoing']) / interval
                    or cached_network_rate['outgoing'],
                }
                cached_stats[app_info['id']]['network_rate'] = app_info['stats']['network']

        return apps_info

    async def run(self):
        interval = self.arg['interval']
        cached_stats = collections.defaultdict(lambda: {
            'memory': 0,
            'cpu': 0,
            'network_actual': {'incoming': 0, 'outgoing': 0},
            'network_rate': {'incoming': 0, 'outgoing': 0},
        })

        while not self._cancel.is_set():
            self.send_event(
                'ADDED', fields=await self.chart_stats(cached_stats)
            )

            await asyncio.sleep(interval)


class ChartReleaseService(Service):

    CHART_RELEASES = {}

    class Config:
        namespace = 'chart.release'

    @accepts(Str('release_name'), roles=['APPS_READ'])
    @returns(List(
        'events', items=[Dict(
            'event',
            Dict(
                'involvedObject',
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
                    self.middleware.create_task(self.poll_chart_release_status(name))

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
            cached_chart_release['data'].pop('config', None)
            self.middleware.send_event(
                'chart.release.query', 'CHANGED', id=name, fields=cached_chart_release['data']
            )
            self.middleware.send_event(
                'chart.release.events', 'CHANGED', id=name, fields={'events': await self.events(name)}
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

    try:
        await middleware.call('chart.release.handle_k8s_event', args)
    except Exception as e:
        middleware.logger.warning('Unhandled exception: %s', e)


async def setup(middleware):
    middleware.event_subscribe('kubernetes.events', chart_release_event)
    middleware.event_register('chart.release.events', 'Application deployment events')
    middleware.register_event_source('chart.release.statistics', ChartReleaseStatsEventSource, roles=['APPS_READ'])
    if await middleware.call('kubernetes.validate_k8s_setup', False):
        middleware.create_task(middleware.call('chart.release.refresh_events_state'))
