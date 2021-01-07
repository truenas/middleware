from middlewared.service import private, Service

from .utils import get_chart_release_from_namespace, is_ix_namespace


class ChartReleaseService(Service):

    CHART_RELEASES = {}

    class Config:
        namespace = 'chart.release'

    @private
    async def refresh_events_state(self):
        ChartReleaseService.CHART_RELEASES = {
            app['name']: app for app in await self.middleware.call('chart.release.query')
        }

    @private
    async def handle_k8s_event(self, k8s_event):
        name = get_chart_release_from_namespace(k8s_event['involved_object']['namespace'])
        chart_release = await self.middleware.call('chart.release.query', [['id', '=', name]])
        if not chart_release:
            # It's possible the chart release got deleted
            return
        else:
            chart_release = chart_release[0]

        if chart_release['status'] != self.CHART_RELEASES.get(name, {}).get('status'):
            # raise event
            self.middleware.send_event('chart.release.events', 'CHANGED', id=name, fields=chart_release)

        ChartReleaseService.CHART_RELEASES[name] = chart_release


async def chart_release_event(middleware, event_type, args):
    args = args['fields']
    if args['involved_object']['kind'] != 'Pod' or not is_ix_namespace(args['involved_object']['namespace']):
        return

    await middleware.call('chart.release.handle_k8s_event', args)


async def setup(middleware):
    middleware.event_subscribe('kubernetes.events', chart_release_event)
    middleware.event_register('chart.release.events', 'Chart Releases events')
