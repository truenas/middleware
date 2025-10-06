import errno
import itertools
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
    ContainerPoolChoicesArgs, ContainerPoolChoicesResult,
)
from middlewared.plugins.zfs.utils import get_encryption_info
from middlewared.pylibvirt import gather_pylibvirt_domains_states, get_pylibvirt_domain_state
from middlewared.service import CRUDService, job, private, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils import BOOT_POOL_NAME_VALID
from middlewared.utils.zfs import query_imported_fast_impl

RE_NAME = re.compile(r'^[a-zA-Z_0-9\-]+$')


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
    idmap_slice = sa.Column(sa.Integer(), nullable=True)
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
        return {
            'states': gather_pylibvirt_domains_states(
                self.middleware,
                rows,
                self.middleware.libvirt_domains_manager.containers_connection,
                lambda container: self.middleware.call_sync(
                    'container.pylibvirt_container', self.extend_container(container),
                ),
            ),
        }

    @private
    async def extend(self, container, context):
        container['status'] = get_pylibvirt_domain_state(context['states'], container)

        self.extend_container(container)

        return container

    @private
    def extend_container(self, container):
        idmap_slice = container.pop('idmap_slice')
        if idmap_slice is None:
            container['idmap'] = None
        elif idmap_slice == 0:
            container['idmap'] = {'type': 'DEFAULT'}
        else:
            container['idmap'] = {
                'type': 'ISOLATED',
                'slice': idmap_slice,
            }

        return container

    @private
    def compress(self, container):
        idmap = container.pop('idmap')
        if idmap is None:
            container['idmap_slice'] = None
        elif idmap['type'] == 'DEFAULT':
            container['idmap_slice'] = 0
        elif idmap['type'] == 'ISOLATED':
            container['idmap_slice'] = idmap['slice']

    @private
    async def validate_pool(self, verrors, schema, pool):
        if pool not in await self.middleware.call("container.pool_choices"):
            verrors.add(
                schema,
                'Pool not found.'
            )

    @private
    async def validate(self, verrors, schema_name, data, old=None):
        if data['uuid'] is None:
            data['uuid'] = str(uuid.uuid4())

        if data['idmap'] is not None:
            if data['idmap']['type'] == 'ISOLATED':
                if data['idmap']['slice'] is None:
                    used_slices = {
                        container['idmap']['slice']
                        for container in await self.middleware.call('container.query')
                        if container['idmap'] is not None and container['idmap']['type'] == 'ISOLATED'
                    }
                    for idmap_slice in itertools.count(1):
                        if idmap_slice not in used_slices:
                            break

                    data['idmap']['slice'] = idmap_slice

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
                'Name can only contain alphanumeric and hyphen characters.'
            )

    @api_method(ContainerCreateArgs, ContainerCreateResult)
    @job(lock=lambda args: f'container_create:{args[0].get("name")}')
    async def do_create(self, job, data):
        """
        Create a Container.
        """
        # Use preferred pool from config if pool not specified
        pool = data.pop('pool') or (await self.middleware.call('lxc.config'))['preferred_pool']
        verrors = ValidationErrors()
        await self.validate(verrors, 'container_create', data)
        if not pool:
            verrors.add(
                'container_create.pool',
                'Either configure a preferred pool in lxc settings or provide a pool name.'
            )
        else:
            await self.validate_pool(verrors, 'container_create.pool', pool)

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

        self.middleware.call_sync('etc.generate', 'libvirt_guests')

    @api_method(ContainerPoolChoicesArgs, ContainerPoolChoicesResult, roles=['VIRT_GLOBAL_READ'])
    async def pool_choices(self):
        """
        Pool choices for container creation.
        """
        pools = {}
        imported_pools = await self.middleware.run_in_thread(query_imported_fast_impl)
        for ds in await self.middleware.call(
            'zfs.resource.query_impl',
            {
                'paths': [
                    p['name']
                    for p in imported_pools.values()
                    if p['name'] not in BOOT_POOL_NAME_VALID
                ],
                'properties': ['encryption'],
            }
        ):
            enc = get_encryption_info(ds['properties'])
            if not enc.locked:
                pools[ds['name']] = ds['name']

        return pools
