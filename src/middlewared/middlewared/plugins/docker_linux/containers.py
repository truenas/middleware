import aiodocker

from middlewared.schema import accepts, Str
from middlewared.service import CallError, CRUDService, filterable
from middlewared.utils import filter_list


class ContainerService(CRUDService):

    class Config:
        namespace = 'docker.container'
        private = True

    @filterable
    async def query(self, filters, options):
        containers = []
        async with aiodocker.Docker() as docker:
            for container in (await docker.containers.list(all=True)):
                containers.append({
                    'id': container.id
                })

        return filter_list(containers, filters, options)

    @accepts(
        Str('container_id'),
    )
    async def do_delete(self, container_id):
        try:
            async with aiodocker.Docker() as docker:
                container = docker.containers.container(container_id)
                await container.delete(force=True)
        except Exception as e:
            raise CallError(f'Unable to delete {container_id!r} container: {e}')
        else:
            return True
