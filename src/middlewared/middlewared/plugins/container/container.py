import errno
import itertools
import os
import re
import uuid

from ixhardware.chassis import TRUENAS_UNKNOWN
from truenas_pylibvirt import DomainDoesNotExistError
from truenas_pylibvirt.domain.base.configuration import parse_numeric_set

from middlewared.api import api_method
from middlewared.api.base import BaseModel, Excluded, excluded_field
from middlewared.api.current import (
    ContainerEntry,
    ContainerCreateArgs, ContainerCreateResult,
    ContainerUpdateArgs, ContainerUpdateResult,
    ContainerDeleteArgs, ContainerDeleteResult,
    ContainerPoolChoicesArgs, ContainerPoolChoicesResult,
    ZFSResourceQuery,
    ZFSResourceSnapshotCloneQuery,
    ZFSResourceSnapshotDestroyQuery,
)
from middlewared.plugins.zfs.exceptions import ZFSPathHasClonesException, ZFSPathNotFoundException
from middlewared.plugins.zfs.utils import get_encryption_info
from middlewared.pylibvirt import gather_pylibvirt_domains_states, get_pylibvirt_domain_state
from middlewared.service import CallError, CRUDService, job, private, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils import BOOT_POOL_NAME_VALID
from middlewared.utils.zfs import query_imported_fast_impl

from .bridge import container_bridge_name
from .nsenter import CAPABILITIES
from .utils import container_dataset

# Based on RFC 1123 hostname rules but with a tighter total-length cap of 100
# characters (RFC 1123 allows 253).  Container names become part of ZFS dataset
# paths (e.g. pool/.truenas_containers/containers/<name>) and ZFS has a practical
# limit of ZFS_MAX_DATASET_NAME_LEN.  Capping at 100 leaves
# comfortable headroom for the dataset path prefix and snapshot names.
RE_NAME = re.compile(
    r"\A"
    r"(?!\d{1,3}(?:\.\d{1,3}){3}\Z)"                    # reject IPv4 dotted-decimal
    r"(?=.{1,100}\Z)"                                    # total length 1-100 (see above)
    r"(?:[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?\.)*"     # zero or more non-final labels
    r"[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?"            # final label (1-63 chars)
    r"\Z",
    re.IGNORECASE,
)


class ContainerModel(sa.Model):
    __tablename__ = 'container_container'

    id = sa.Column(sa.Integer(), primary_key=True)
    uuid = sa.Column(sa.Text())
    name = sa.Column(sa.Text())
    description = sa.Column(sa.Text())
    autostart = sa.Column(sa.Boolean())
    time = sa.Column(sa.Text())
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
            'bridge_name': container_bridge_name(self),
        }

    @private
    async def extend(self, container, context):
        devices = await self.middleware.call(
            'container.device.query',
            [('container', '=', container['id'])],
            {'force_sql_filters': True},
        )
        has_nic = any(d['attributes']['dtype'] == 'NIC' for d in devices)

        container.update({
            'status': get_pylibvirt_domain_state(context['states'], container),
            'devices': devices,
            'default_network': None if has_nic else context['bridge_name'],
        })

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
        container.pop('default_network', None)
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
        if not await self.license_active():
            verrors.add(
                f'{schema_name}.name',
                'System is not licensed to use containers.'
            )

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

        if invalid_caps := set(data['capabilities_state']) - CAPABILITIES:
            verrors.add(
                f'{schema_name}.capabilities_state',
                f'Invalid capabilities: {", ".join(sorted(invalid_caps))}'
            )

        # Validate cpuset format if provided
        if data.get('cpuset'):
            if '_' in data['cpuset']:
                verrors.add(f'{schema_name}.cpuset', 'Underscores are not allowed in CPU set values')
            else:
                try:
                    parse_numeric_set(data['cpuset'])
                except ValueError as e:
                    verrors.add(
                        f'{schema_name}.cpuset',
                        f'Invalid cpuset format: {e}'
                    )

        filters = [('name', '=', data['name'])]
        if old:
            filters.append(('id', '!=', old['id']))

        if await self.middleware.call('container.query', filters):
            verrors.add(
                f'{schema_name}.name',
                'A container with this name already exists.', errno.EEXIST
            )
        elif not RE_NAME.match(data['name']):
            verrors.add(
                f'{schema_name}.name',
                'Name must be a valid hostname (up to 100 characters total): 1-63 characters per label, '
                'only letters, digits, and hyphens within each label, labels separated by dots, '
                'and must not be an IPv4 address.'
            )

    @api_method(
        ContainerCreateArgs,
        ContainerCreateResult,
        audit='Container create',
        audit_extended=lambda data: data['name'],
    )
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
        data['dataset'] = os.path.join(container_dataset(pool), f'containers/{data["name"]}')

        # Populate dataset
        if pool == image_snapshot.split('@')[0].split('/')[0]:  # noqa
            # The container is in the same pool as images. We can just clone the image.
            # Both the image snapshot and the destination live under
            # .truenas_containers, which is an internal (delete-guarded) path, and
            # pool.snapshot.clone has no bypass passthrough - so clone directly.
            await self.call2(
                self.s.zfs.resource.snapshot.clone_impl,
                ZFSResourceSnapshotCloneQuery(
                    snapshot=image_snapshot,  # noqa
                    dataset=data['dataset'],
                    bypass=True,
                ),
            )
            await self.call2(self.s.zfs.resource.mount, data['dataset'])
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
            await self.call2(
                self.s.zfs.resource.snapshot.destroy_impl,
                ZFSResourceSnapshotDestroyQuery(path=f'{data["dataset"]}@{source_snapshot}', bypass=True),
            )

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

    @api_method(
        ContainerUpdateArgs,
        ContainerUpdateResult,
        audit='Container update',
        audit_callback=True,
    )
    async def do_update(self, audit_callback, id_, data):
        """
        Update a Container.
        """
        old = await self.get_instance(id_)
        del old['devices']
        new = old.copy()
        new.update(data)
        audit_callback(new['name'])

        verrors = ValidationErrors()
        await self.validate(verrors, 'container_update', new, old=old)
        verrors.check()

        name_changed = old['name'] != new['name']
        if name_changed:
            if old['status']['state'] != 'STOPPED':
                raise CallError('Container must be stopped before renaming.')

            old_dataset = old['dataset']
            new_dataset = old_dataset[:old_dataset.rfind('/') + 1] + new['name']
            await self.call2(self.s.zfs.resource.rename, old_dataset, new_dataset)
            new['dataset'] = new_dataset

        for key in ('status', ):
            new.pop(key, None)

        self.compress(new)
        await self.middleware.call('datastore.update', 'container.container', id_, new)

        if old['shutdown_timeout'] != new['shutdown_timeout']:
            await self.middleware.call('etc.generate', 'libvirt_guests')

        return await self.get_instance(id_)

    @api_method(
        ContainerDeleteArgs,
        ContainerDeleteResult,
        audit='Container delete',
        audit_callback=True,
    )
    @job(lock='container_delete')
    def do_delete(self, job, audit_callback, id_, options):
        """
        Delete a Container.
        """
        # A single global lock serializes deletes so that fan-out siblings cloned
        # from one migrated image don't race each other's last-clone image GC.
        container = self.middleware.call_sync("container.get_instance", id_)
        audit_callback(container['name'])

        if container['status']['state'] != 'STOPPED':
            if not options['force']:
                raise CallError(
                    f'Container {container["name"]!r} is {container["status"]["state"].lower()}. Stop it first, '
                    f'or pass force=True to stop and delete it.'
                )
            self.middleware.call_sync('container.stop', id_, {'force': True}).wait_sync(raise_error=True)

        # Read the origin image (if this container clones a migrated Incus image)
        # before destroying the clone - the origin is unreadable afterwards.
        migrated_origin = self.migrated_container_origin(container['dataset'])

        # Destroy the dataset first and only remove the DB/libvirt records once it is
        # actually gone, so a failed destroy never orphans the dataset with no
        # container row pointing at it. recursive=True mirrors the apps stack so a
        # container that has snapshots can still be removed; bypass=True because the
        # dataset lives under the now delete-guarded .truenas_containers.
        try:
            failed = self.call_sync2(
                self.s.zfs.resource.destroy_impl, container['dataset'], recursive=True, bypass=True,
            )[0]
        except ZFSPathNotFoundException:
            # Dataset already gone (e.g. a victim of a legacy .ix-virt deletion);
            # fall through to clean up the now-dangling records.
            failed = None
        if failed is not None:
            raise CallError(f'Failed to delete container {container["name"]!r} dataset: {failed}')

        self.delete_container_from_db_and_libvirt(container)
        self.middleware.call_sync('etc.generate', 'libvirt_guests')

        if migrated_origin is not None:
            self.gc_migrated_origin_image(migrated_origin)

    @private
    def migrated_container_origin(self, container_ds):
        """Return the origin snapshot of `container_ds` iff it clones a migrated
        Incus image (tagged ``truenas:origin=incus-migration``), else ``None``.

        Only tagged images are eligible for last-clone garbage collection, so a
        native image-cache dataset is never reaped.
        """
        try:
            resources = self.call_sync2(
                self.s.zfs.resource.query_impl,
                ZFSResourceQuery(paths=[container_ds], properties=['origin']),
            )
            if not resources:
                return None

            origin = resources[0]['properties']['origin']['value']
            if origin in (None, '', 'none'):
                return None

            image = self.call_sync2(
                self.s.zfs.resource.query_impl,
                ZFSResourceQuery(paths=[origin.split('@')[0]], get_user_properties=True),
            )
            if not image:
                return None

            user_properties = image[0].get('user_properties') or {}
            if user_properties.get('truenas:origin') != 'incus-migration':
                return None

            return origin
        except Exception:
            self.logger.warning(
                '%s: failed to read origin for image garbage collection', container_ds, exc_info=True,
            )
            return None

    @private
    def gc_migrated_origin_image(self, origin_snapshot):
        """Garbage-collect a migrated origin image once its last clone is gone.

        Attempts to destroy the origin ``@readonly`` snapshot; if other container
        clones still depend on it, ZFS raises ``ZFSPathHasClonesException`` and it
        is left in place. Otherwise the image dataset is destroyed recursively so
        any snapshots it accumulated (e.g. from a periodic snapshot task over
        ``.truenas_containers``) do not block reclaim - this is safe because we
        only get here once the origin snapshot is confirmed clone-free, so no live
        container clones the image. Best-effort: a GC failure never fails the delete.
        """
        try:
            self.call_sync2(
                self.s.zfs.resource.snapshot.destroy_impl,
                ZFSResourceSnapshotDestroyQuery(path=origin_snapshot, bypass=True),
            )
        except ZFSPathHasClonesException:
            # Other containers still clone this image; keep it.
            return
        except Exception:
            self.logger.warning(
                '%s: failed to garbage-collect migrated image snapshot', origin_snapshot, exc_info=True,
            )
            return

        origin_dataset = origin_snapshot.split('@')[0]
        try:
            self.call_sync2(self.s.zfs.resource.destroy_impl, origin_dataset, recursive=True, bypass=True)
        except Exception:
            self.logger.warning(
                '%s: failed to destroy garbage-collected migrated image', origin_dataset, exc_info=True,
            )

    @private
    def delete_container_from_db_and_libvirt(self, container):
        pylibvirt_container = self.middleware.call_sync("container.pylibvirt_container", container)
        try:
            self.middleware.libvirt_domains_manager.containers.delete(pylibvirt_container)
        except DomainDoesNotExistError:
            pass

        for device in container['devices']:
            self.middleware.call_sync('datastore.delete', 'container.device', device['id'])

        self.middleware.call_sync('datastore.delete', 'container.container', container['id'])

    @api_method(ContainerPoolChoicesArgs, ContainerPoolChoicesResult, roles=['CONTAINER_READ'])
    async def pool_choices(self):
        """
        Pool choices for container creation.
        """
        pools = {}
        imported_pools = await self.middleware.run_in_thread(query_imported_fast_impl)
        for ds in await self.call2(
            self.s.zfs.resource.query_impl,
            ZFSResourceQuery(
                paths=[
                    p['name']
                    for p in imported_pools.values()
                    if p['name'] not in BOOT_POOL_NAME_VALID
                ],
                properties=['encryption'],
            )
        ):
            enc = get_encryption_info(ds['properties'])
            if not enc.locked:
                pools[ds['name']] = ds['name']

        return pools

    @private
    async def license_active(self):
        """
        If this is iX enterprise hardware and has NOT been licensed to run containers
        then this will return False, otherwise this will return true.
        """
        system_chassis = await self.middleware.call('truenas.get_chassis_hardware')
        if system_chassis == TRUENAS_UNKNOWN or 'MINI' in system_chassis:
            # 1. if it's not iX branded hardware
            # 2. OR if it's a MINI, then allow containers/vms
            return True

        return await self.middleware.call('system.feature_enabled', 'APPS')
