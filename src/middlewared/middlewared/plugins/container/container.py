from middlewared.api import api_method
from middlewared.api.current import (
    ContainerEntry,
    ContainerCreateArgs, ContainerCreateResult,
    ContainerUpdateArgs, ContainerUpdateResult,
    ContainerDeleteArgs, ContainerDeleteResult,
)
from middlewared.service import CRUDService, private, ValidationErrors
from middlewared.plugins.vm.crud import VMCRUDMixin
from middlewared.plugins.vm.vms import LIBVIRT_LOCK
import middlewared.sqlalchemy as sa

from middlewared.plugins.vm.vm_supervisor import VMSupervisorMixin


class ContainerModel(sa.Model):
    __tablename__ = 'container_container'

    id = sa.Column(sa.Integer(), primary_key=True)
    uuid = sa.Column(sa.Text())
    name = sa.Column(sa.Text())
    description = sa.Column(sa.Text())
    vcpus = sa.Column(sa.Integer())
    memory = sa.Column(sa.Integer())
    autostart = sa.Column(sa.Boolean())
    time = sa.Column(sa.Text())
    cores = sa.Column(sa.Integer(), default=1)
    threads = sa.Column(sa.Integer(), default=1)
    cpuset = sa.Column(sa.Text(), default=None, nullable=True)
    shutdown_timeout = sa.Column(sa.Integer())
    dataset = sa.Column(sa.Text())
    init = sa.Column(sa.Text())


class ContainerService(CRUDService, VMCRUDMixin, VMSupervisorMixin):

    class Config:
        namespace = 'container'
        datastore = 'container.container'
        datastore_extend = 'container.extend'
        datastore_extend_context = 'container.extend_context'
        cli_namespace = 'service.container'
        role_prefix = 'CONTAINER'
        entry = ContainerEntry

    @api_method(ContainerCreateArgs, ContainerCreateResult)
    async def do_create(self, data):
        """
        Create a Container.
        """
        async with LIBVIRT_LOCK:
            await self.middleware.run_in_thread(self._check_setup_connection)

        verrors = ValidationErrors()
        await self.common_validation(verrors, 'container_create', data)
        verrors.check()

        container_id = await self.middleware.call('datastore.insert', 'container.container', data)
        await self.middleware.run_in_thread(self._add, container_id, 'container')
        await self.middleware.call('etc.generate', 'libvirt_guests')

        return await self.get_instance(container_id)

    @private
    async def common_validation(self, verrors, schema_name, data, old=None):
        await self.base_common_validation('container', verrors, schema_name, data, old)

    @api_method(ContainerUpdateArgs, ContainerUpdateResult)
    async def do_update(self, id_, data):
        """
        Update a Container.
        """
        old = await self.get_instance(id_)
        new = old.copy()
        new.update(data)

        await self.pre_update(old, new, 'Container')

        verrors = ValidationErrors()
        await self.common_validation(verrors, 'container_update', new, old=old)
        verrors.check()

        for key in ('status', ):
            new.pop(key, None)

        await self.middleware.call('datastore.update', 'container.container', id_, new)

        vm_data = await self.get_instance(id_)
        if new['name'] != old['name']:
            await self.middleware.run_in_thread(self._rename_domain, old, vm_data)

        if old['shutdown_timeout'] != new['shutdown_timeout']:
            await self.middleware.call('etc.generate', 'libvirt_guests')

        return await self.get_instance(id_)

    @api_method(ContainerDeleteArgs, ContainerDeleteResult)
    async def do_delete(self, id_, data):
        """
        Delete a Container.
        """
        pass  # FIXME
