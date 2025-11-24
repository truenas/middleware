import errno

import docker.errors
from dateutil.parser import parse, ParserError
from docker.api.client import APIClient

from middlewared.api.current import (
    AppContainerLogsFollowTailEventSourceArgs, AppContainerLogsFollowTailEventSourceEvent,
)
from middlewared.event import EventSource
from middlewared.service import CallError, Service

from .ix_apps.utils import AppState
from .ix_apps.docker.utils import get_docker_client


def _fixed_stream_raw_result(self, response, chunk_size=None, decode=True):
    """
    Original docker-py bug: chunk_size defaults to 1, causing character-by-character
    streaming for TTY-enabled containers. This fix changes the default to None,
    which allows the underlying requests library to use proper buffering.
    """
    self._raise_for_status(response)
    socket = self._get_raw_response_socket(response)
    self._disable_socket_timeout(socket)
    yield from response.iter_content(chunk_size, decode)


APIClient._stream_raw_result = _fixed_stream_raw_result


class AppContainerLogsFollowTailEventSource(EventSource):

    """
    Retrieve logs of a container/service in an app.
    """
    args = AppContainerLogsFollowTailEventSourceArgs
    event = AppContainerLogsFollowTailEventSourceEvent
    roles = ['APPS_READ']

    def __init__(self, *args, **kwargs):
        super(AppContainerLogsFollowTailEventSource, self).__init__(*args, **kwargs)
        self.logs_stream = None

    def validate_log_args(self, app_name, container_id):
        app = self.middleware.call_sync('app.get_instance', app_name)
        if app['state'] not in (AppState.CRASHED.value, AppState.RUNNING.value, AppState.DEPLOYING.value):
            raise CallError(f'Unable to retrieve logs of stopped {app_name!r} app')

        if not any(c['id'] == container_id for c in app['active_workloads']['container_details']):
            raise CallError(f'Container "{container_id}" not found in app "{app_name}"', errno=errno.ENOENT)

    def run_sync(self):
        app_name = self.arg['app_name']
        container_id = self.arg['container_id']
        tail_lines = self.arg['tail_lines'] or 'all'

        self.validate_log_args(app_name, container_id)
        with get_docker_client() as docker_client:
            try:
                container = docker_client.containers.get(container_id)
            except docker.errors.NotFound:
                raise CallError(f'Container "{container_id}" not found')

            self.logs_stream = container.logs(stream=True, follow=True, timestamps=True, tail=tail_lines)

            for log_entry in map(bytes.decode, self.logs_stream):
                # Event should contain a timestamp in RFC3339 format, we should parse it and supply it
                # separately so UI can highlight the timestamp giving us a cleaner view of the logs
                timestamp = log_entry.split(maxsplit=1)[0].strip()
                try:
                    timestamp = str(parse(timestamp))
                except (TypeError, ParserError):
                    timestamp = None
                else:
                    log_entry = log_entry.split(maxsplit=1)[-1].lstrip()

                self.send_event('ADDED', fields={'data': log_entry, 'timestamp': timestamp})

    async def cancel(self):
        await super().cancel()
        if self.logs_stream:
            await self.middleware.run_in_thread(self.logs_stream.close)

    async def on_finish(self):
        self.logs_stream = None


class AppService(Service):

    class Config:
        event_sources = {
            'app.container_log_follow': AppContainerLogsFollowTailEventSource,
        }
