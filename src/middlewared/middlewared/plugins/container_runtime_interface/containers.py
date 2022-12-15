from middlewared.schema import accepts, Str
from middlewared.service import CallError, CRUDService, filterable
from middlewared.utils import filter_list

from .client import ContainerdClient


class ContainerService(CRUDService):

    class Config:
        namespace = 'docker.container'
        private = True

    @filterable
    def query(self, filters, options):
        containers = []
        with ContainerdClient('container') as client:
            for container in client.list_containers():
                containers.append({
                    'id': container['id'],
                })

        return filter_list(containers, filters, options)

    @accepts(
        Str('container_id'),
    )
    def do_delete(self, container_id):
        try:
            with ContainerdClient('container') as client:
                client.remove_container(container_id)
        except Exception as e:
            raise CallError(f'Unable to delete {container_id!r} container: {e}')
        else:
            return True
