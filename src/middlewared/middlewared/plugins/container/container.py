import errno
import re
import uuid

from truenas_pylibvirt import DomainDoesNotExistError

from middlewared.api import api_method
from middlewared.api.base import BaseModel, Excluded, excluded_field
from middlewared.api.current import (
    ContainerEntry,
    ContainerCreateArgs, ContainerCreateResult,
    ContainerUpdateArgs, ContainerUpdateResult,
    ContainerDeleteArgs, ContainerDeleteResult,
)
from middlewared.plugins.account_.constants import CONTAINER_ROOT_UID
from middlewared.service import CRUDService, job, private, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils.zfs import query_imported_fast_impl

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
    idmap = sa.Column(sa.Text(), nullable=True)
    idmap_target = sa.Column(sa.Integer(), nullable=True)
    idmap_count = sa.Column(sa.Integer(), nullable=True)
    capabilities_policy = sa.Column(sa.Text())
    capabilities_state = sa.Column(sa.JSON(dict))


class ContainerCreateWithDataset(ContainerCreateArgs.model_fields['container_create'].annotation):
    pool: Excluded = excluded_field()
    image: Excluded = excluded_field()
    dataset: str


class ContainerCreateWithDatasetArgs(BaseModel):
    container_create: ContainerCreateWithDataset


class ContainerCreateWithDatasetResult(ContainerCreateResult):
    pass


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
        if container['idmap'] == 'ISOLATED':
            container['idmap'] = {
                'target': container['idmap_target'],
                'count': container['idmap_count'],
            }

        del container['idmap_target']
        del container['idmap_count']

        return container

    @private
    def compress(self, container):
        if isinstance(container['idmap'], dict):
            container['idmap_target'] = container['idmap']['target']
            container['idmap_count'] = container['idmap']['count']
            container['idmap'] = 'ISOLATED'
        else:
            container['idmap_target'] = None
            container['idmap_count'] = None

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

        if isinstance(data['idmap'], dict):
            if data['idmap']['target'] < CONTAINER_ROOT_UID:
                verrors.add(
                    f'{schema_name}.idmap.target',
                    f'Cannot be less than {CONTAINER_ROOT_UID}.'
                )

    @api_method(ContainerCreateArgs, ContainerCreateResult)
    @job(lock=lambda args: f'container_create:{args[0].get("name")}')
    async def do_create(self, job, data):
        """
        Create a Container.
        """
        verrors = ValidationErrors()
        await self.validate(verrors, 'container_create', data)
        verrors.check()

        pool = data.pop('pool')
        if not await self.middleware.run_in_thread(query_imported_fast_impl, [pool]):
            verrors.add('container_create.pool', 'Pool not found.')
            verrors.check()

        image = data.pop('image')
        try:
            image_snapshot = await job.wrap(await self.middleware.call('container.image.pull', pool, image))
        except ValidationErrors as image_verrors:
            verrors.add_child('container_create.image', image_verrors)
            verrors.check()

        await self.middleware.call('container.ensure_datasets', pool)
        data['dataset'] = f'{pool}/.truenas_containers/containers/{data["name"]}'

        # Populate dataset
        if pool == image_snapshot.split('@')[0].split('/')[0]:  # noqa
            # The container is in the same pool as images. We can just clone the image.
            await self.middleware.call("pool.snapshot.clone", {
                "snapshot": image_snapshot,  # noqa
                "dataset_dst": data['dataset']
            })
        else:
            # The container is on the different pool. Let's replicate the image.
            source_dataset, source_snapshot = image_snapshot.split('@', 1)  # noqa
            await job.wrap(await self.middleware.call(
                'replication.run_onetime', {
                    'direction': 'PUSH',
                    'transport': 'LOCAL',
                    'source_datasets': [source_dataset],
                    'target_dataset': data['dataset'],
                    'recursive': True,
                    'name_regex': source_snapshot,
                    'retention_policy': 'SOURCE',
                    'replicate': True,
                    'readonly': 'IGNORE',
                }
            ))
            await self.middleware.call('zfs.snapshot.delete', f'{data["dataset"]}@{source_snapshot}')

        return await self.create_with_dataset(data)

    @api_method(ContainerCreateWithDatasetArgs, ContainerCreateWithDatasetResult, private=True)
    async def create_with_dataset(self, data):
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

        self.middleware.call_sync('pool.dataset.delete', container['dataset'])
