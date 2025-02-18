# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from middlewared.service import job, private, Service

from .connection import KMIPServerMixin


class KMIPService(Service, KMIPServerMixin):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.zfs_keys = {}

    @private
    async def zfs_keys_pending_sync(self):
        config = await self.middleware.call('kmip.config')
        for ds in await self.middleware.call('datastore.query', 'storage.encrypteddataset'):
            if config['enabled'] and config['manage_zfs_keys'] and (
                ds['encryption_key'] or ds['name'] not in self.zfs_keys
            ):
                return True
            elif any(not config[k] for k in ('enabled', 'manage_zfs_keys')) and ds['kmip_uid']:
                return True
        return False

    @private
    def push_zfs_keys(self, ids=None):
        datasets = self.middleware.call_sync(
            'datastore.query', 'storage.encrypteddataset', [['id', 'in', ids]] if ids else []
        )
        existing_datasets = {ds['name']: ds for ds in self.middleware.call_sync('pool.dataset.query')}
        failed = []
        with self._connection(self.middleware.call_sync('kmip.connection_config')) as conn:
            for ds in filter(lambda d: d['name'] in existing_datasets, datasets):
                if not ds['encryption_key']:
                    # We want to make sure we have the KMIP server's keys and in-memory keys in sync
                    try:
                        if ds['name'] in self.zfs_keys and self.middleware.call_sync(
                            'zfs.dataset.check_key', ds['name'], {'key': self.zfs_keys[ds['name']]}
                        ):
                            continue
                        else:
                            key = self._retrieve_secret_data(ds['kmip_uid'], conn)
                    except Exception as e:
                        self.middleware.logger.debug(f'Failed to retrieve key for {ds["name"]}: {e}')
                    else:
                        self.zfs_keys[ds['name']] = key
                    continue

                self.zfs_keys[ds['name']] = ds['encryption_key']
                destroy_successful = False
                if ds['kmip_uid']:
                    # This needs to be revoked and destroyed
                    destroy_successful = self._revoke_and_destroy_key(ds['kmip_uid'], conn, self.middleware.logger)
                    if not destroy_successful:
                        self.middleware.logger.debug(f'Failed to destroy key from KMIP Server for {ds["name"]}')
                try:
                    uid = self._register_secret_data(ds['name'], self.zfs_keys[ds['name']], conn)
                except Exception:
                    failed.append(ds['name'])
                    update_data = {'kmip_uid': None} if destroy_successful else {}
                else:
                    update_data = {'encryption_key': None, 'kmip_uid': uid}
                if update_data:
                    self.middleware.call_sync('datastore.update', 'storage.encrypteddataset', ds['id'], update_data)
        self.zfs_keys = {k: v for k, v in self.zfs_keys.items() if k in existing_datasets}
        return failed

    @private
    def pull_zfs_keys(self):
        datasets = self.middleware.call_sync('datastore.query', 'storage.encrypteddataset', [['kmip_uid', '!=', None]])
        existing_datasets = {ds['name']: ds for ds in self.middleware.call_sync('pool.dataset.query')}
        failed = []
        connection_successful = self.middleware.call_sync('kmip.test_connection')
        for ds in filter(lambda d: d['name'] in existing_datasets, datasets):
            try:
                if ds['encryption_key']:
                    key = ds['encryption_key']
                elif ds['name'] in self.zfs_keys and self.middleware.call_sync(
                    'zfs.dataset.check_key', ds['name'], {'key': self.zfs_keys[ds['name']]}
                ):
                    key = self.zfs_keys[ds['name']]
                elif connection_successful:
                    with self._connection(self.middleware.call_sync('kmip.connection_config')) as conn:
                        key = self._retrieve_secret_data(ds['kmip_uid'], conn)
                else:
                    raise Exception('Failed to sync dataset')
            except Exception:
                failed.append(ds['name'])
            else:
                update_data = {'encryption_key': key, 'kmip_uid': None}
                self.middleware.call_sync('datastore.update', 'storage.encrypteddataset', ds['id'], update_data)
                self.zfs_keys.pop(ds['name'], None)
                if connection_successful:
                    self.middleware.call_sync('kmip.delete_kmip_secret_data', ds['kmip_uid'])
        self.zfs_keys = {k: v for k, v in self.zfs_keys.items() if k in existing_datasets}
        return failed

    @private
    @job(lock=lambda args: f'kmip_sync_zfs_keys_{args}')
    def sync_zfs_keys(self, job, ids=None):
        if not self.middleware.call_sync('kmip.zfs_keys_pending_sync'):
            return
        config = self.middleware.call_sync('kmip.config')
        conn_successful = self.middleware.call_sync('kmip.test_connection', None, True)
        if config['enabled'] and config['manage_zfs_keys']:
            if conn_successful:
                failed = self.push_zfs_keys(ids)
            else:
                return
        else:
            failed = self.pull_zfs_keys()
        if failed:
            self.middleware.call_sync(
                'alert.oneshot_create', 'KMIPZFSDatasetsSyncFailure', {'datasets': ','.join(failed)}
            )
        self.middleware.call_hook_sync('kmip.zfs_keys_sync')
        return failed

    @private
    async def clear_sync_pending_zfs_keys(self):
        to_remove = []
        for ds in await self.middleware.call(
            'datastore.query', 'storage.encrypteddataset', [['kmip_uid', '!=', None]]
        ):
            if ds['encryption_key']:
                await self.middleware.call('datastore.update', 'storage.encrypteddataset', {'kmip_uid': None})
            else:
                to_remove.append(ds['id'])
        await self.middleware.call('datastore.delete', 'storage.encrypteddataset', [['id', 'in', to_remove]])
        self.zfs_keys = {}

    @private
    def initialize_zfs_keys(self, connection_success):
        locked_datasets = [ds['id'] for ds in self.middleware.call_sync('zfs.dataset.locked_datasets')]
        for ds in self.middleware.call_sync('datastore.query', 'storage.encrypteddataset',):
            if ds['encryption_key']:
                self.zfs_keys[ds['name']] = ds['encryption_key']
            elif ds['kmip_uid'] and connection_success:
                try:
                    with self._connection(self.middleware.call_sync('kmip.connection_config')) as conn:
                        key = self._retrieve_secret_data(ds['kmip_uid'], conn)
                except Exception:
                    self.middleware.logger.debug(f'Failed to retrieve key for {ds["name"]}')
                else:
                    self.zfs_keys[ds['name']] = key
            if ds['name'] in self.zfs_keys and ds['name'] in locked_datasets:
                self.middleware.call_sync('pool.dataset.unlock', ds['name'])

    @private
    async def retrieve_zfs_keys(self):
        return self.zfs_keys

    @private
    async def reset_zfs_key(self, dataset, kmip_uid):
        self.zfs_keys.pop(dataset, None)
        if kmip_uid:
            try:
                await self.middleware.call('kmip.delete_kmip_secret_data', kmip_uid)
            except Exception as e:
                self.middleware.logger.debug(
                    f'Failed to remove encryption key from KMIP server for "{dataset}" Dataset: {e}'
                )
        await self.middleware.call_hook('kmip.zfs_keys_sync')

    @private
    async def update_zfs_keys(self, zfs_keys):
        self.zfs_keys = zfs_keys
