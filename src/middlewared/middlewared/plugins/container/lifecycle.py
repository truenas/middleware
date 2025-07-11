from middlewared.api import api_method
from middlewared.api.current import (
    ContainerStartArgs, ContainerStartResult,
)
from middlewared.service import Service

from middlewared.plugins.vm.vm_supervisor import VMSupervisorMixin


class ContainerService(Service, VMSupervisorMixin):
    @api_method(ContainerStartArgs, ContainerStartResult, roles=['CONTAINER_WRITE'])
    async def start(self, id_):
        container = await self.middleware.call('container.get_instance', id_)

        await self.middleware.run_in_thread(self._start, container['name'], 'container')
