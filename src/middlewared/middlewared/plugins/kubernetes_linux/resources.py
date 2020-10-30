from middlewared.service import accepts, Service


class KubernetesService(Service):

    @accepts()
    async def events(self):
        return (await self.middleware.call('k8s.node.config')).get('events', [])
