import aiodocker

from middlewared.schema import accepts, Str
from middlewared.service import CRUDService, filterable


class ContainerService(CRUDService):

    class Config:
        private = True

    @filterable
    async def query(self, filters, options):
        containers = []
        async with aiodocker.Docker() as docker:
            for container in (await docker.containers.list()):
                containers.append({
                    'id': container.id
                })

        return containers

    @accepts(
        Str('container_id'),
    )
    async def do_delete(self, container_id):
        async with aiodocker.Docker() as docker:
            container = docker.containers.container(container_id)
            await container.delete(force=True)
