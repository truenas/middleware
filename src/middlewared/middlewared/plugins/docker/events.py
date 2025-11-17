from middlewared.api.base import Event
from middlewared.api.current import DockerEventsAddedEvent
from middlewared.plugins.apps.ix_apps.docker.utils import get_docker_client, PROJECT_KEY
from middlewared.service import Service


class DockerEventService(Service):

    class Config:
        namespace = 'docker.events'
        private = True
        events = [
            Event(
                name='docker.events',
                description='Docker container events',
                roles=['DOCKER_READ'],
                models={'ADDED': DockerEventsAddedEvent},
            )
        ]

    def setup(self):
        if not self.middleware.call_sync('docker.state.validate', False):
            return

        try:
            self.process()
        except Exception:
            if not self.middleware.call('service.started', 'docker'):
                # This is okay and can happen when docker is stopped
                return
            raise

    def process(self):
        with get_docker_client() as docker_client:
            self.process_internal(docker_client)

    def process_internal(self, client):
        for container_event in client.events(
            decode=True, filters={
                'type': ['container'],
                'event': [
                    'create', 'destroy', 'detach', 'die', 'health_status', 'kill', 'unpause',
                    'oom', 'pause', 'rename', 'resize', 'restart', 'start', 'stop', 'update',
                ]
            }
        ):
            if not isinstance(container_event, dict):
                continue

            if project := container_event.get('Actor', {}).get('Attributes', {}).get(PROJECT_KEY):
                self.middleware.send_event('docker.events', 'ADDED', id=project, fields=container_event)


async def setup(middleware):
    # We are going to check in setup docker events if setting up events is relevant or not
    middleware.create_task(middleware.call('docker.events.setup'))
