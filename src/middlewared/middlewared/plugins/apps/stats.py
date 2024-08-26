import time

from middlewared.event import EventSource
from middlewared.schema import Dict, Int, Str
from middlewared.service import CallError
from middlewared.validators import Range

from .ix_apps.docker.stats import list_resources_stats_by_project
from .ix_apps.utils import get_app_name_from_project_name


class AppStatsEventSource(EventSource):

    """
    Retrieve statistics of apps.
    """
    ACCEPTS = Dict(
        Int('interval', default=2, validators=[Range(min_=2)]),
    )
    RETURNS = Dict(
        Str('data', required=True),
        Str('timestamp', required=True, null=True)
    )

    def run_sync(self):
        if not self.middleware.call_sync('docker.state.validate', False):
            raise CallError('Apps are not available')

        interval = self.arg['interval']
        while not self._cancel_sync.is_set():
            self.send_event('ADDED', fields={
                get_app_name_from_project_name(project_name): stats
                for project_name, stats in list_resources_stats_by_project().items()
            })
            time.sleep(interval)


def setup(middleware):
    middleware.register_event_source('app.stats', AppStatsEventSource, roles=['APPS_READ'])
