import time

from middlewared.api.current import AppStatsEventSourceArgs, AppStatsEventSourceEvent
from middlewared.event import EventSource
from middlewared.plugins.docker.state_utils import Status
from middlewared.service import CallError, Service

from .ix_apps.docker.stats import list_resources_stats_by_project
from .stats_util import normalize_projects_stats


class AppStatsEventSource(EventSource):
    """
    Retrieve statistics of apps.
    """

    args = AppStatsEventSourceArgs
    event = AppStatsEventSourceEvent
    roles = ['APPS_READ']

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
                if self.middleware.call_sync('docker.status')['status'] != Status.RUNNING.value:
                    return

                raise


class AppService(Service):

    class Config:
        event_sources = {
            'app.stats': AppStatsEventSource,
        }
