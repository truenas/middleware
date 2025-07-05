import errno
import re
import uuid

from truenas_pylibvirt import DomainDoesNotExistError

from middlewared.api import api_method
from middlewared.api.current import (
    ContainerEntry,
    ContainerCreateArgs, ContainerCreateResult,
    ContainerUpdateArgs, ContainerUpdateResult,
    ContainerDeleteArgs, ContainerDeleteResult,
)
from middlewared.plugins.vm.utils import get_default_status
from middlewared.service import CallError, CRUDService, private, ValidationErrors
import middlewared.sqlalchemy as sa

RE_NAME = re.compile(r'^[a-zA-Z_0-9]+$')


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


class ContainerService(CRUDService):

    class Config:
        namespace = 'container'
        datastore = 'container.container'
        datastore_extend = 'container.extend'
        datastore_extend_context = 'container.extend_context'
        cli_namespace = 'service.container'
        role_prefix = 'CONTAINER'
        entry = ContainerEntry

    @private
    def extend_context(self, rows, extra):
        status = {}
        if rows:
            shutting_down = self.middleware.call_sync('system.state') == 'SHUTTING_DOWN'
            if not shutting_down:
                uuid_to_container = {row['uuid']: row for row in rows}
                connection = self.middleware.libvirt_domains_manager.containers_connection
                for domain in connection.list_domains():
                    uuid = domain.name()
                    if container := uuid_to_container.get(uuid):
                        status[uuid] = self._domain_state(
                            connection,
                            domain,
                            self.middleware.call_sync('container.pylibvirt_container', container),
                        )

        return {
            'status': status,
        }

    def _domain_state(self, connection, libvirt_domain, domain):
        return {
            'state': 'RUNNING' if libvirt_domain.isActive() else 'STOPPED',
            'pid': domain.pid(),
            'domain_state': connection.domain_state(libvirt_domain).value,
        }

    @private
    async def extend(self, container, context):
        container['status'] = context['status'].get(container['uuid']) or {
            'state': 'STOPPED',
            'pid': None,
            'domain_state': None,
        }

        return container

    @private
    async def validate(self, verrors, schema_name, data, old=None):
        if not data.get('uuid'):
            data['uuid'] = str(uuid.uuid4())

        if 'name' in data:
            filters = [('name', '=', data['name'])]
            if old:
                filters.append(('id', '!=', old['id']))

            if await self.middleware.call('container.query', filters):
                verrors.add(
                    f'{schema_name}.name',
                    'A container with this name already exists.', errno.EEXIST
                )
            elif not RE_NAME.search(data['name']):
                verrors.add(
                    f'{schema_name}.name',
                    'Only alphanumeric characters are allowed.'
                )

    @api_method(ContainerCreateArgs, ContainerCreateResult)
    async def do_create(self, data):
        """
        Create a Container.
        """
        verrors = ValidationErrors()
        await self.validate(verrors, 'container_create', data)
        verrors.check()

        container_id = await self.middleware.call('datastore.insert', 'container.container', data)
        await self.middleware.call('etc.generate', 'libvirt_guests')

        return await self.get_instance(container_id)

    @api_method(ContainerUpdateArgs, ContainerUpdateResult)
    async def do_update(self, id_, data):
        """
        Update a Container.
        """
        old = await self.get_instance(id_)
        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()
        await self.validate(verrors, 'container_update', new, old=old)
        verrors.check()

        for key in ('status', ):
            new.pop(key, None)

        await self.middleware.call('datastore.update', 'container.container', id_, new)

        if old['shutdown_timeout'] != new['shutdown_timeout']:
            await self.middleware.call('etc.generate', 'libvirt_guests')

        return await self.get_instance(id_)

    @api_method(ContainerDeleteArgs, ContainerDeleteResult)
    def do_delete(self, id_):
        """
        Delete a Container.
        """
        container = self.middleware.call_sync("container.get_instance", id_)

        pylibvirt_container = self.middleware.call_sync("container.pylibvirt_container", container)
        try:
            self.middleware.libvirt_domains_manager.containers.delete(pylibvirt_container)
        except DomainDoesNotExistError:
            pass

        self.middleware.call_sync('datastore.delete', 'container.container', id_)
