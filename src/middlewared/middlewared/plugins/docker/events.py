from middlewared.service import Service


class DockerEventService(Service):

    class Config:
        namespace = 'docker.events'
        private = True

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
        pass


async def setup(middleware):
    middleware.event_register('docker.events', 'Docker container events')
    # We are going to check in setup docker events if setting up events is relevant or not
    middleware.create_task(middleware.call('docker.events.setup'))
