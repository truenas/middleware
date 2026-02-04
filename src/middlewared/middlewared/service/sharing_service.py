from typing import Protocol, TYPE_CHECKING

from middlewared.async_validators import check_path_resides_within_volume
from middlewared.plugins.zfs_.validation_utils import check_zvol_in_boot_pool_using_path
from middlewared.utils.mount import resolve_dataset_path
from middlewared.utils.path import FSLocation, path_location

from .crud_service import CRUDService
from .decorators import pass_app, private
if TYPE_CHECKING:
    from middlewared.main import Middleware
    from . import ValidationErrors


class PathModel(Protocol):
    dataset: str | None
    relative_path: str | None


class SharingTaskService(CRUDService):

    path_field = 'path'
    allowed_path_types = [FSLocation.LOCAL]
    enabled_field = 'enabled'
    locked_field = 'locked'
    locked_alert_class = NotImplemented
    share_task_type = NotImplemented
    path_resolution_filters = None
    """Describe which share entries should attempt to resolve their dataset field from path when dataset=None. By
    default, all entries will attempt to resolve their datasets. Filters must use the field names found in the database
    table (including `datastore_prefix`)."""

    def __init__(self, middleware: 'Middleware'):
        super().__init__(middleware)
        # Register path resolution hooks for all SharingTaskService subclasses
        middleware.register_hook('dataset.post_unlock', self.resolve_paths, sync=True)
        middleware.register_hook('pool.post_import', self.resolve_paths, sync=True)

    @classmethod
    @private
    async def resolve_paths(cls, middleware: 'Middleware', *_args, **_kwargs) -> None:
        """
        Attempt resolution of NULL dataset paths.

        Note: *_args and **_kwargs are accepted but unused. They're required because hooks
        are called with varying arguments (pool.post_import passes pool, dataset.post_unlock
        passes datasets=[...]), but this hook queries for NULL paths independently.

        IMPORTANT: Used by migration/0018_resolve_dataset_paths.py
        """
        config = cls._config
        namespace = config.namespace
        datastore = config.datastore
        prefix = config.datastore_prefix

        # Query entries with unresolved dataset paths
        unresolved = await middleware.call(
            'datastore.query',
            datastore,
            [
                [prefix + 'dataset', '=', None],
                *(cls.path_resolution_filters or [])
            ]
        )
        if not unresolved:
            middleware.logger.info(f"No {namespace} entries to resolve")
            return

        for entry in unresolved:
            try:
                entry_id = entry['id']
                path = entry[prefix + cls.path_field]

                dataset, relative_path = await middleware.run_in_thread(resolve_dataset_path, path, middleware)
                if dataset:
                    # Successfully resolved - update database
                    await middleware.call(
                        'datastore.update',
                        datastore,
                        entry_id,
                        {
                            prefix + 'dataset': dataset,
                            prefix + 'relative_path': relative_path
                        }
                    )
                    middleware.logger.info(f"Resolved {namespace} id={entry_id}: {dataset}@'{relative_path}'")
                else:
                    # Cannot resolve yet (encrypted dataset, etc.) - leave as NULL
                    middleware.logger.info(f"Deferred {namespace} id={entry_id}: {path}")

            except Exception as e:
                middleware.logger.debug(
                    f"Failed to resolve {namespace} id={entry_id} path={path}: {e}"
                )

    @private
    async def get_path_field(self, data):
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

        return {
            'service_extend': se,
            'retrieve_locked_info': extra.get('retrieve_locked_info', True)
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
    async def validate_path_field(
        self, data: PathModel | dict, schema: str, verrors: 'ValidationErrors', *, split_path: bool = False
    ) -> 'ValidationErrors':
        """Validate the path field and optionally split it into dataset and relative_path components.
                                            
        Performs path validation based on location type (LOCAL/EXTERNAL/ZVOL) and optionally                                                                                                                                                                                                                                                   
        resolves the path to its ZFS dataset components."""
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

        else:
            self.logger.error('%s: unknown location type', loc.name)
            raise NotImplementedError

        return verrors

    @private
    async def sharing_task_determine_locked(self, data):
        path = await self.get_path_field(data)
        if path_location(path) is not FSLocation.LOCAL:
            return False

        return await self.middleware.call(
            'pool.dataset.path_in_locked_datasets', path
        )

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
        await self.middleware.call(
            'alert.oneshot_create', self.locked_alert_class,
            {**share_task, 'identifier': await self.human_identifier(share_task), 'type': self.share_task_type}
        )

    @private
    async def remove_locked_alert(self, share_task_id):
        await self.middleware.call(
            'alert.oneshot_delete', self.locked_alert_class, f'"{self.share_task_type}_{share_task_id}"'
        )

    @pass_app(message_id=True)
    async def update(self, app, audit_callback, message_id, id_, data):
        rv = await super().update(app, audit_callback, message_id, id_, data)
        if not rv[self.enabled_field] or not rv[self.locked_field]:
            await self.remove_locked_alert(rv['id'])
        return rv

    update.audit_callback = True

    @pass_app(message_id=True)
    async def delete(self, app, audit_callback, message_id, id_, *args):
        rv = await super().delete(app, audit_callback, message_id, id_, *args)
        await self.remove_locked_alert(id_)
        return rv

    delete.audit_callback = True


class SharingService(SharingTaskService):
    locked_alert_class = 'ShareLocked'

    @private
    async def human_identifier(self, share_task):
        return share_task['name']


class TaskPathService(SharingTaskService):
    locked_alert_class = 'TaskLocked'

    @private
    async def human_identifier(self, share_task):
        return await self.get_path_field(share_task)
