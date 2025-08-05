import os

from middlewared.service import CallError, Service

from .ix_apps.path import get_app_parent_volume_ds_name
from .utils import DatasetDefaults


class AppSchemaActions(Service):

    class Config:
        namespace = 'app.schema.action'
        private = True

    async def update_volumes(self, app_name, volumes):
        app_volume_ds = get_app_parent_volume_ds_name(
            (await self.middleware.call('docker.config'))['dataset'], app_name
        )

        user_wants = {app_volume_ds: {'properties': {}}} | {os.path.join(app_volume_ds, v['name']): v for v in volumes}
        existing_datasets = {
            d['name'] for d in await self.middleware.call(
                'zfs.resource.query_impl', {'paths': list(user_wants), 'properties': None}
            )
        }
        for create_ds in sorted(set(user_wants) - existing_datasets):
            await self.middleware.call(
                'zfs.dataset.create', {
                    'properties': user_wants[create_ds]['properties'] | DatasetDefaults.create_time_props(),
                    'name': create_ds, 'type': 'FILESYSTEM',
                }
            )
            await self.middleware.call('zfs.dataset.mount', create_ds)

    async def apply_acls(self, acls_to_apply):
        bulk_job = await self.middleware.call(
            'core.bulk', 'filesystem.add_to_acl', [[acls_to_apply[acl_path]] for acl_path in acls_to_apply],
        )
        await bulk_job.wait()

        failures = []
        for status, acl_path in zip(bulk_job.result, acls_to_apply):
            if status['error']:
                failures.append((acl_path, status['error']))

        if failures:
            err_str = 'Failed to apply ACLs to the following paths: \n'
            for index, entry in enumerate(failures):
                err_str += f'{index + 1}) {entry[0]}: {entry[1]}\n'
            raise CallError(err_str)
