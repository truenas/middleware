import os.path

from middlewared.async_validators import check_path_resides_within_volume
from middlewared.plugins.zfs_.validation_utils import check_zvol_in_boot_pool_using_path
from middlewared.plugins.zfs.zvol_utils import zvol_path_to_name
from middlewared.utils.mount import statmount
from middlewared.utils.path import FSLocation, path_location

from .crud_service import CRUDService
from .decorators import pass_app, private


class SharingTaskService(CRUDService):

    path_field = 'path'
    allowed_path_types = [FSLocation.LOCAL]
    enabled_field = 'enabled'
    locked_field = 'locked'
    locked_alert_class = NotImplemented
    share_task_type = NotImplemented

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
    async def validate_path_field(self, data, schema, verrors):
        name = f'{schema}.{self.path_field}'
        path = await self.get_path_field(data)
        await self.validate_zvol_path(verrors, name, path)
        loc = path_location(path)

        if loc not in self.allowed_path_types:
            verrors.add(name, f'{loc.name}: path type is not allowed.')

        elif loc is FSLocation.EXTERNAL:
            await self.validate_external_path(verrors, name, path)

        elif loc is FSLocation.LOCAL:
            await self.validate_local_path(verrors, name, path)

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
    async def sharing_task_extend(self, data: dict, context: dict) -> dict:
        # Perform datastore_extend
        if self._config.datastore_extend:
            args = [data] + ([context['service_extend']] if self._config.datastore_extend_context else [])
            data = await self.middleware.call(self._config.datastore_extend, *args)

        # Set locked field
        if context['retrieve_locked_info']:
            data[self.locked_field] = await self.middleware.call(
                f'{self._config.namespace}.sharing_task_determine_locked', data
            )
        else:
            data[self.locked_field] = None

        # Calculate dataset and relative_path from path field
        try:
            path = data[self.path_field]
            if path.startswith('/dev/zvol/'):
                # Handle zvol
                data.update(dataset=zvol_path_to_name(path), relative_path='')
            elif path.startswith('zvol/'):
                # /dev/ is stripped sometimes
                data.update(dataset=path[5:], relative_path='')
            else:
                # Handle dataset
                mntinfo = await self.middleware.run_in_thread(statmount, path=path, as_dict=False)

                relative_path = os.path.relpath(path, mntinfo.mnt_point)
                if relative_path == '.':
                    relative_path = ''

                data.update(dataset=mntinfo.sb_source, relative_path=relative_path)
        except Exception:
            data.update(dataset=None, relative_path=None)

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
