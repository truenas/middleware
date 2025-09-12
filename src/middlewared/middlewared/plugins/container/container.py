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
from middlewared.service import CRUDService, private, ValidationErrors
import middlewared.sqlalchemy as sa

RE_NAME = re.compile(r'^[a-zA-Z_0-9]+$')


class ContainerModel(sa.Model):
    __tablename__ = 'container_container'

    id = sa.Column(sa.Integer(), primary_key=True)
    uuid = sa.Column(sa.Text())
    name = sa.Column(sa.Text())
    description = sa.Column(sa.Text())
    vcpus = sa.Column(sa.Integer(), nullable=True)
    memory = sa.Column(sa.Integer(), nullable=True)
    autostart = sa.Column(sa.Boolean())
    time = sa.Column(sa.Text())
    cores = sa.Column(sa.Integer(), nullable=True)
    threads = sa.Column(sa.Integer(), nullable=True)
    cpuset = sa.Column(sa.Text(), nullable=True)
    shutdown_timeout = sa.Column(sa.Integer())
    dataset = sa.Column(sa.Text())
    init = sa.Column(sa.Text())
    initdir = sa.Column(sa.Text(), nullable=True)
    initenv = sa.Column(sa.JSON(dict))
    inituser = sa.Column(sa.Text(), nullable=True)
    initgroup = sa.Column(sa.Text(), nullable=True)
    idmap_uid_target = sa.Column(sa.Integer(), nullable=True)
    idmap_uid_count = sa.Column(sa.Integer(), nullable=True)
    idmap_gid_target = sa.Column(sa.Integer(), nullable=True)
    idmap_gid_count = sa.Column(sa.Integer(), nullable=True)
    capabilities_policy = sa.Column(sa.Text())
    capabilities_state = sa.Column(sa.JSON(dict))


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
                try:
                    for domain in connection.list_domains():
                        uuid = domain.name()
                        if container := uuid_to_container.get(uuid):
                            status[uuid] = self._domain_state(
                                connection,
                                domain,
                                self.middleware.call_sync(
                                    'container.pylibvirt_container', self.extend_container(container.copy()),
                                ),
                            )
                except Exception:
                    self.logger.warning("Unhandled exception in `container.extend_context`", exc_info=True)

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

        self.extend_container(container)

        return container

    @private
    def extend_container(self, container):
        if container['idmap_uid_target'] is not None:
            container['idmap'] = {
                'uid': {'target': container['idmap_uid_target'], 'count': container['idmap_uid_count']},
                'gid': {'target': container['idmap_gid_target'], 'count': container['idmap_gid_count']},
            }
        else:
            container['idmap'] = None

        del container['idmap_uid_target']
        del container['idmap_uid_count']
        del container['idmap_gid_target']
        del container['idmap_gid_count']

        return container

    @private
    def compress(self, container):
        if container['idmap']:
            container['idmap_uid_target'] = container['idmap']['uid']['target']
            container['idmap_uid_count'] = container['idmap']['uid']['count']
            container['idmap_gid_target'] = container['idmap']['gid']['target']
            container['idmap_gid_count'] = container['idmap']['gid']['count']
        else:
            container['idmap_uid_target'] = None
            container['idmap_uid_count'] = None
            container['idmap_gid_target'] = None
            container['idmap_gid_count'] = None

        del container['idmap']

    @private
    async def validate(self, verrors, schema_name, data, old=None):
        if not data.get('uuid'):
            data['uuid'] = str(uuid.uuid4())

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

        if not await self.middleware.call(
            "pool.dataset.query", [["name", "=", data["dataset"]], ["type", "=", "FILESYSTEM"]]
        ):
            verrors.add(f"{schema_name}.dataset", "The dataset must exist and be a filesystem.")

        filters = [('dataset', '=', data['dataset'])]
        if old:
            filters.append(('id', '!=', old['id']))

        if await self.middleware.call('container.query', filters):
            verrors.add(
                f'{schema_name}.dataset',
                'Another container is already using this dataset.', errno.EEXIST
            )

    @api_method(ContainerCreateArgs, ContainerCreateResult)
    async def do_create(self, data):
        """
        Create a Container.
        """
        verrors = ValidationErrors()
        await self.validate(verrors, 'container_create', data)
        verrors.check()

        self.compress(data)
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

        self.compress(new)
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
