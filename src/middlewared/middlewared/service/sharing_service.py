import asyncio
from typing import TYPE_CHECKING, Iterable, Protocol, Sequence

from middlewared.alert.base import OneShotAlertClass
from middlewared.alert.source.sharing_tasks import ShareLockedAlert, TaskLockedAlert
from middlewared.async_validators import check_path_resides_within_volume
from middlewared.plugins.zfs_.validation_utils import check_zvol_in_boot_pool_using_path
from middlewared.utils.mount import resolve_dataset_path
from middlewared.utils.path import FSLocation, path_location

from .crud_service import CRUDService
from .decorators import pass_app, private
from .sharing_task_service_part import (
    MOUNT_RESOLVE_DELAY,
    LocalPathInfo,
    resolve_stored_paths,
    send_resolved_events,
    validate_path_service_share,
    validate_path_service_write,
)

if TYPE_CHECKING:
    from middlewared.main import Middleware

    from . import ValidationErrors


class PathModel(Protocol):
    dataset: str | None
    relative_path: str | None


class SharingTaskService[E](CRUDService[E]):

    path_field = 'path'
    allowed_path_types = [FSLocation.LOCAL]
    enabled_field = 'enabled'
    locked_field = 'locked'
    locked_alert_class: type[OneShotAlertClass]
    share_task_type: str
    path_resolution_filters: Iterable[Sequence] | None = None
    include_tier_info = False
    """Describe which share entries have a path to resolve their dataset fields from. By default, all entries do.
    Filters must use the field names found in the database table (including `datastore_prefix`)."""
    readonly_field: str | None = None
    """The flag that makes the share or task read-only for its local path, or None where nothing does: what
    `local_path_info` reads unless overridden."""

    def __init__(self, middleware: 'Middleware'):
        super().__init__(middleware)
        self._mounted_unresolved: set[str] = set()
        # Register path resolution hooks for all SharingTaskService subclasses
        middleware.register_hook('dataset.post_unlock', self.resolve_paths, sync=True)
        middleware.register_hook('pool.post_import', self.resolve_paths, sync=True)
        middleware.register_hook('zfs.dataset.mounted', self.resolve_mounted_paths, sync=False)

    @classmethod
    @private
    async def resolve_paths(
        cls, middleware: 'Middleware', *_args, datasets: list[dict] | None = None, mountpoints: set[str] | None = None,
    ) -> None:
        """
        Resolve paths again and store the dataset and relative path each one is in.

        Every path is resolved unless `datasets` (the datasets ``dataset.post_unlock`` passes) or `mountpoints`
        (from `resolve_mounted_paths`) narrow it to the paths they can have changed. Positional arguments are
        accepted but unused: ``pool.post_import`` passes the pool, and every path is resolved after an import.

        IMPORTANT: Used by migration/0018_resolve_dataset_paths.py
        """
        config = cls._config
        changed = await resolve_stored_paths(
            middleware, config.namespace, config.datastore, config.datastore_prefix, cls.path_field,
            cls.path_resolution_filters,
            datasets=None if datasets is None else [ds['name'] for ds in datasets],
            mountpoints=mountpoints,
        )
        if changed and config.event_send:
            try:
                entries = await middleware.call(
                    f'{config.namespace}.query', [[config.datastore_primary_key, 'in', changed]],
                    {'force_sql_filters': True},
                )
                send_resolved_events(middleware, config.namespace, entries)
            except Exception:
                # Raising would have the hook's arguments logged, and dataset.post_unlock's carry encryption keys
                middleware.logger.error(
                    '%s: failed to send change events for %r', config.namespace, changed, exc_info=True
                )

    @private
    async def resolve_mounted_paths(self, middleware: 'Middleware', data: dict) -> None:
        """``zfs.dataset.mounted`` hook: resolve the paths under a dataset that was just mounted, together with
        those under any other dataset mounted in the next `MOUNT_RESOLVE_DELAY` seconds."""
        waiting = bool(self._mounted_unresolved)
        self._mounted_unresolved.add(data['mountpoint'])
        if waiting:
            return

        await asyncio.sleep(MOUNT_RESOLVE_DELAY)
        mountpoints, self._mounted_unresolved = self._mounted_unresolved, set()
        await self.resolve_paths(middleware, mountpoints=mountpoints)

    @private
    async def get_path_field(self, data) -> str:
        if isinstance(data, dict):
            # FIXME: Remove all the cases where this is dict
            return data[self.path_field]
        else:
            return getattr(data, self.path_field)

    @private
    async def sharing_task_extend_context(self, rows, extra):
        if extra.get('select'):
            select_fields = []
            for entry in extra['select']:
                if isinstance(entry, list) and entry:
                    select_fields.append(entry[0])
                elif isinstance(entry, str):
                    # Just being extra sure so that we don't crash
                    select_fields.append(entry)

            if self.locked_field not in select_fields:
                extra['retrieve_locked_info'] = False

        se = None
        if self._config.datastore_extend_context:
            se = await self.middleware.call(self._config.datastore_extend_context, rows, extra)

        tier_map = {}
        if self.include_tier_info:
            datasets = [r['dataset'] for r in rows if r.get('dataset')]
            if datasets:
                tier_map = await self.call2(self.s.zfs.tier.bulk_get_tier_info, datasets)

        return {
            'service_extend': se,
            'retrieve_locked_info': extra.get('retrieve_locked_info', True),
            'tier_map': tier_map,
        }

    @private
    async def validate_external_path(self, verrors, name, path):
        # Services with external paths must implement their own
        # validation here because we can't predict what is required.
        raise NotImplementedError

    @private
    async def validate_zvol_path(self, verrors, name, path):
        if check_zvol_in_boot_pool_using_path(path):
            verrors.add(name, 'Disk residing in boot pool cannot be consumed and is not supported')

    @private
    async def validate_local_path(self, verrors, name, path):
        await check_path_resides_within_volume(verrors, self.middleware, name, path)

    @private
    async def local_path_info(self, data) -> LocalPathInfo | None:
        """Whether the share or task only reads its local path, and the field that decides it -- a share's
        read-only flag, a task's direction -- or None where it always writes there. What `validate_path_field`
        passes to `validate_path_service_write`."""
        if self.readonly_field is None:
            return None
        if isinstance(data, dict):
            # FIXME: Remove all the cases where this is dict
            readonly = data[self.readonly_field]
        else:
            readonly = getattr(data, self.readonly_field)
        return LocalPathInfo(readonly_field=self.readonly_field, readonly=bool(readonly))

    @private
    async def validate_path_field(
        self, data: PathModel | dict, schema: str, verrors: 'ValidationErrors', *, split_path: bool = False
    ) -> 'ValidationErrors':
        """Validate the path field and optionally split it into dataset and relative_path components.

        Performs path validation based on location type (LOCAL/EXTERNAL/ZVOL) and optionally
        resolves the path to its ZFS dataset components. A local path whose writes belong to another
        service is refused unless `local_path_info` says this share or task only reads it."""
        name = f'{schema}.{self.path_field}'
        path = await self.get_path_field(data)
        await self.validate_zvol_path(verrors, name, path)
        loc = path_location(path)

        if loc not in self.allowed_path_types:
            verrors.add(name, f'{loc.name}: path type is not allowed.')

        elif loc is FSLocation.EXTERNAL:
            await self.validate_external_path(verrors, name, path)
            if split_path:
                if isinstance(data, dict):
                    # FIXME: Remove when this method no longer passed a dict
                    data.update(dataset=None, relative_path=None)
                else:
                    data.dataset = data.relative_path = None

        elif loc is FSLocation.LOCAL:
            await self.validate_local_path(verrors, name, path)
            if split_path:
                ds, rel_path = await self.middleware.run_in_thread(
                    resolve_dataset_path, path, self.middleware
                )
                if isinstance(data, dict):
                    # FIXME: Remove when this method no longer passed a dict
                    data.update(dataset=ds, relative_path=rel_path)
                else:
                    data.dataset = ds
                    data.relative_path = rel_path
            await validate_path_service_write(
                self.middleware, verrors, schema, self.path_field, path, data, await self.local_path_info(data)
            )

        else:
            self.logger.error('%s: unknown location type', loc.name)
            raise NotImplementedError

        return verrors

    @private
    async def sharing_task_determine_locked(self, data):
        path = await self.get_path_field(data)
        if path_location(path) is not FSLocation.LOCAL:
            return False

        # When the dataset is resolved, pass it directly to avoid iterating over
        # relative_path subdirectory components, which are not datasets and always
        # produce spurious EZFS_NOENT lookups.
        return await self.call2(self.s.zfs.resource.path_is_locked, data.get('dataset') or path)

    @private
    async def sharing_task_extend(self, data, context):
        args = [data] + ([context['service_extend']] if self._config.datastore_extend_context else [])

        if self._config.datastore_extend:
            data = await self.middleware.call(self._config.datastore_extend, *args)

        if context['retrieve_locked_info']:
            data[self.locked_field] = await self.middleware.call(
                f'{self._config.namespace}.sharing_task_determine_locked', data
            )
        else:
            data[self.locked_field] = None

        if self.include_tier_info and 'tier' not in data:
            data['tier'] = context['tier_map'].get(data.get('dataset'))

        return data

    @private
    async def get_options(self, options):
        return {
            **(await super().get_options(options)),
            'extend': f'{self._config.namespace}.sharing_task_extend',
            'extend_context': f'{self._config.namespace}.sharing_task_extend_context',
        }

    @private
    async def human_identifier(self, share_task):
        raise NotImplementedError

    @private
    async def generate_locked_alert(self, share_task_id):
        share_task = await self.get_instance(share_task_id)
        await self.call2(
            self.s.alert.oneshot_create, self.locked_alert_class(
                type=self.share_task_type,
                identifier=await self.human_identifier(share_task),
                id=share_task['id'],
            )
        )

    @private
    async def remove_locked_alert(self, share_task_id):
        await self.call2(
            self.s.alert.oneshot_delete, self.locked_alert_class.config.name, f'{self.share_task_type}_{share_task_id}'
        )

    @pass_app(message_id=True)
    async def update(self, app, audit_callback, message_id, id_, data):
        rv = await super().update(app, audit_callback, message_id, id_, data)
        if isinstance(rv, dict):
            # FIXME: Remove all the cases where this is dict
            enabled = rv[self.enabled_field]
            locked = rv[self.locked_field]
        else:
            enabled = getattr(rv, self.enabled_field)
            locked = getattr(rv, self.locked_field)
        if not enabled or not locked:
            await self.remove_locked_alert(id_)
        return rv

    update.audit_callback = True

    @pass_app(message_id=True)
    async def delete(self, app, audit_callback, message_id, id_, *args):
        rv = await super().delete(app, audit_callback, message_id, id_, *args)
        await self.remove_locked_alert(id_)
        return rv

    delete.audit_callback = True


class SharingService[E](SharingTaskService[E]):
    locked_alert_class = ShareLockedAlert
    include_tier_info = False

    @private
    async def validate_path_field(
        self, data: PathModel | dict, schema: str, verrors: 'ValidationErrors', *, split_path: bool = False
    ) -> 'ValidationErrors':
        await super().validate_path_field(data, schema, verrors, split_path=split_path)
        await validate_path_service_share(
            self.middleware, verrors, schema, self.path_field, await self.get_path_field(data), data,
            self.readonly_field,
        )
        return verrors

    @private
    async def human_identifier(self, share_task):
        if isinstance(share_task, dict):
            # FIXME: Remove all the cases where this is dict
            return share_task['name']
        else:
            return share_task.name


class TaskPathService[E](SharingTaskService[E]):
    locked_alert_class = TaskLockedAlert

    @private
    async def human_identifier(self, share_task):
        return await self.get_path_field(share_task)
