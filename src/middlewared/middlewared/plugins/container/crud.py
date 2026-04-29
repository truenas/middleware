from __future__ import annotations

import errno
import itertools
import os
import re
from typing import TYPE_CHECKING, Any, TypeVar
import uuid

from truenas_pylibvirt import DomainDoesNotExistError
from truenas_pylibvirt.domain.base.configuration import parse_numeric_set
from truenas_pylibvirt.nsexec import ALL_CAPABILITIES as CAPABILITIES

from middlewared.api.base import BaseModel, Excluded, excluded_field
from middlewared.api.current import (
    ContainerCreate,
    ContainerCreateResult,
    ContainerEntry,
    ContainerUpdate,
    QueryOptions,
    ZFSResourceSnapshotDestroyQuery,
)
from middlewared.pylibvirt import gather_pylibvirt_domains_states, get_pylibvirt_domain_state
from middlewared.service import CallError, CRUDServicePart, ValidationErrors
import middlewared.sqlalchemy as sa

from .bridge import container_bridge_name
from .dataset import ensure_datasets
from .info import license_active, pool_choices
from .lifecycle import pylibvirt_container
from .utils import container_dataset

if TYPE_CHECKING:
    from middlewared.job import Job
    from middlewared.utils.types import AuditCallback


ContainerDataT = TypeVar('ContainerDataT', bound=ContainerEntry)


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


class ContainerCreateWithDataset(ContainerCreate):
    pool: Excluded = excluded_field()  # type: ignore[no-untyped-call]
    image: Excluded = excluded_field()  # type: ignore[no-untyped-call]
    dataset: str  # type: ignore[assignment]


class ContainerCreateWithDatasetArgs(BaseModel):
    container_create: ContainerCreateWithDataset
    """Container create with dataset parameters."""


class ContainerCreateWithDatasetResult(ContainerCreateResult):
    pass


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


class ContainerServicePart(CRUDServicePart[ContainerEntry]):
    _datastore = 'container.container'
    _entry = ContainerEntry

    def extend_context_sync(self, rows: list[dict[str, Any]], extra: dict[str, Any]) -> dict[str, Any]:
        return {
            'states': gather_pylibvirt_domains_states(
                self.middleware,
                rows,
                self.middleware.libvirt_domains_manager.containers_connection,
                lambda container: pylibvirt_container(self, self.extend_container(container)),
            ),
            'bridge_name': container_bridge_name(self),
        }

    async def extend(self, data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        devices = await self.call2(
            self.s.container.device.query,
            [('container', '=', data['id'])],
            QueryOptions(force_sql_filters=True),
        )
        has_nic = any(d.attributes.dtype == 'NIC' for d in devices)

        data.update({
            'status': get_pylibvirt_domain_state(context['states'], data),
            'devices': devices,
            'default_network': None if has_nic else context['bridge_name'],
        })

        self.extend_container(data)

        return data

    async def compress(self, data: dict[str, Any]) -> dict[str, Any]:
        data.pop('default_network', None)
        idmap = data.pop('idmap')
        if idmap is None:
            data['idmap_slice'] = None
        elif idmap['type'] == 'DEFAULT':
            data['idmap_slice'] = 0
        elif idmap['type'] == 'ISOLATED':
            data['idmap_slice'] = idmap['slice']

        return data

    def extend_container(self, container: dict[str, Any]) -> dict[str, Any]:
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

    async def create_with_dataset(self, data: ContainerCreateWithDataset) -> ContainerEntry:
        verrors = ValidationErrors()
        data = await self.validate(verrors, 'container_create', data)
        verrors.check()

        entry = await self._create(data.model_dump())
        await self.middleware.call('etc.generate', 'libvirt_guests')
        return entry

    async def do_create(self, job: Job, data: ContainerCreate) -> ContainerEntry:
        verrors = ValidationErrors()
        pool = data.pool or (await self.call2(self.s.lxc.config)).preferred_pool
        if not pool:
            verrors.add(
                'container_create.pool',
                'Either configure a preferred pool in lxc settings or provide a pool name.'
            )
        elif pool not in await pool_choices(self):
            verrors.add(
                'container_create.pool',
                'Pool not found.'
            )
        data = await self.validate(verrors, 'container_create', data)
        verrors.check()
        assert pool is not None

        image = data.image.model_dump()
        try:
            image_snapshot = await job.wrap(await self.call2(
                self.s.container.image.pull, pool, image,
            ))
        except ValidationErrors as image_verrors:
            verrors.add_child('container_create.image', image_verrors)
            verrors.check()

        await ensure_datasets(self, pool)
        dataset = os.path.join(container_dataset(pool), f'containers/{data.name}')

        # Populate dataset
        if pool == image_snapshot.split('@')[0].split('/')[0]:  # noqa
            # The container is in the same pool as images. We can just clone the image.
            await self.middleware.call("pool.snapshot.clone", {
                "snapshot": image_snapshot,  # noqa
                "dataset_dst": dataset
            })
        else:
            # The container is on the different pool. Let's replicate the image.
            source_dataset, source_snapshot = image_snapshot.split('@', 1)  # noqa
            await job.wrap(await self.middleware.call(
                'replication.run_onetime', {
                    'direction': 'PUSH',
                    'transport': 'LOCAL',
                    'source_datasets': [source_dataset],
                    'target_dataset': dataset,
                    'recursive': True,
                    'name_regex': source_snapshot,
                    'retention_policy': 'SOURCE',
                    'replicate': True,
                    'readonly': 'IGNORE',
                }
            ))
            await self.call2(
                self.s.zfs.resource.snapshot.destroy_impl,
                ZFSResourceSnapshotDestroyQuery(path=f'{dataset}@{source_snapshot}'),
            )

        entry = await self._create(data.model_dump(exclude={'pool', 'image'}) | {'dataset': dataset})
        await self.middleware.call('etc.generate', 'libvirt_guests')
        return entry

    async def do_update(
        self, id_: int, data: ContainerUpdate, *, audit_callback: AuditCallback,
    ) -> ContainerEntry:
        old = await self.get_instance(id_)
        new = old.model_copy(update=data.model_dump(exclude_unset=True))
        audit_callback(new.name)

        verrors = ValidationErrors()
        new = await self.validate(verrors, 'container_update', new, old=old)
        verrors.check()

        name_changed = old.name != new.name
        if name_changed:
            if old.status.state == 'RUNNING':
                raise CallError('Container must be stopped before renaming.')

            old_dataset = old.dataset
            new_dataset = old_dataset[:old_dataset.rfind('/') + 1] + new.name
            await self.call2(self.s.zfs.resource.rename, old_dataset, new_dataset)
            new = new.model_copy(update={'dataset': new_dataset})

        entry = await self._update(id_, new.model_dump(exclude={'id', 'devices', 'status'}))

        if old.shutdown_timeout != new.shutdown_timeout:
            await self.middleware.call('etc.generate', 'libvirt_guests')

        return entry

    def do_delete(self, id_: int, *, audit_callback: AuditCallback) -> None:
        container = self.get_instance__sync(id_)
        audit_callback(container.name)

        self.delete_container_from_db_and_libvirt(container)
        self.call_sync2(self.s.zfs.resource.destroy_impl, container.dataset)
        self.middleware.call_sync('etc.generate', 'libvirt_guests')

    def delete_container_from_db_and_libvirt(self, container: ContainerEntry) -> None:
        pylibvirt_container_obj = pylibvirt_container(self, container.model_dump(by_alias=True))
        try:
            self.middleware.libvirt_domains_manager.containers.delete(pylibvirt_container_obj)
        except DomainDoesNotExistError:
            pass

        for device in container.devices:
            self.middleware.call_sync('datastore.delete', 'container.device', device.id)

        self.run_coroutine(self._delete(container.id))

    async def validate(
        self, verrors: ValidationErrors, schema_name: str, data: ContainerDataT, old: ContainerEntry | None = None,
    ) -> ContainerDataT:
        if not await license_active(self):
            verrors.add(
                f'{schema_name}.name',
                'System is not licensed to use containers.'
            )

        if data.uuid is None:
            data = data.model_copy(update={'uuid': str(uuid.uuid4())})

        if data.idmap is not None:
            if data.idmap.type == 'ISOLATED':
                if data.idmap.slice is None:
                    used_slices = {
                        container.idmap.slice
                        for container in await self.query([], QueryOptions())
                        if container.idmap is not None and container.idmap.type == 'ISOLATED'
                    }
                    idmap_slice = next(
                        s for s in itertools.count(1) if s not in used_slices
                    )
                    data = data.model_copy(update={
                        'idmap': data.idmap.model_copy(update={'slice': idmap_slice}),
                    })

        if invalid_caps := set(data.capabilities_state) - CAPABILITIES:
            verrors.add(
                f'{schema_name}.capabilities_state',
                f'Invalid capabilities: {", ".join(sorted(invalid_caps))}'
            )

        if data.cpuset:
            if '_' in data.cpuset:
                verrors.add(f'{schema_name}.cpuset', 'Underscores are not allowed in CPU set values')
            else:
                try:
                    parse_numeric_set(data.cpuset)
                except ValueError as e:
                    verrors.add(
                        f'{schema_name}.cpuset',
                        f'Invalid cpuset format: {e}'
                    )

        filters: list[tuple[str, str, Any]] = [('name', '=', data.name)]
        if old:
            filters.append(('id', '!=', old.id))

        if await self.query(filters, QueryOptions()):
            verrors.add(
                f'{schema_name}.name',
                'A container with this name already exists.', errno.EEXIST
            )
        elif not RE_NAME.match(data.name):
            verrors.add(
                f'{schema_name}.name',
                'Name must be a valid hostname (up to 100 characters total): 1-63 characters per label, '
                'only letters, digits, and hyphens within each label, labels separated by dots, '
                'and must not be an IPv4 address.'
            )

        return data
