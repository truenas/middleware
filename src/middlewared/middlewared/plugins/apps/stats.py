import time

from middlewared.event import EventSource
from middlewared.schema import Dict, Int, Str, List
from middlewared.service import CallError
from middlewared.validators import Range

from .ix_apps.docker.stats import list_resources_stats_by_project
from .stats_util import normalize_projects_stats


class AppStatsEventSource(EventSource):

    """
    Retrieve statistics of apps.
    """

    ACCEPTS = Dict(
        Int('interval', default=2, validators=[Range(min_=2)]),
    )
    RETURNS = List(
        'apps_stats',
        items=[
            Dict(
                'stats',
                Str('app_name'),
                Int('cpu_usage', description='Percentage of cpu used by an app'),
                Int('memory', description='Current memory(in bytes) used by an app'),
                List(
                    'networks',
                    items=[
                        Dict(
                            'interface_stats',
                            Str('interface_name', description='Name of the interface use by the app'),
                            Int('rx_bytes', description='Received bytes per interval by an interface'),
                            Int('tx_bytes', description='Transmitted bytes per interval by an interface')
                        ),
                    ]
                ),
                Dict(
                    'blkio',
                    Int('read', description='Blkio read bytes'),
                    Int('write', description='Blkio write bytes')
                )
            )
        ]
    )

    def run_sync(self):
        if not self.middleware.call_sync('docker.state.validate', False):
            raise CallError('Apps are not available')

        old_projects_stats = list_resources_stats_by_project()
        interval = self.arg['interval']
        time.sleep(interval)

        while not self._cancel_sync.is_set():
            try:
                project_stats = list_resources_stats_by_project()
                self.send_event(
                    'ADDED', fields=normalize_projects_stats(project_stats, old_projects_stats, interval)
                )
                old_projects_stats = project_stats
                time.sleep(interval)
            except Exception:
                if self.middleware.call_sync('docker.config')['pool'] is None:
                    return
                if self.middleware.call_sync('service.started', 'docker') is False:
                    self.middleware.logger.error('Unable to retrieve app stats as docker service has been stopped')
                    return

                raise


def setup(middleware):
    middleware.register_event_source('app.stats', AppStatsEventSource, roles=['APPS_READ'])
