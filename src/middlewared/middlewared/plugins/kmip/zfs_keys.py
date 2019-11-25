from middlewared.service import ConfigService, job, private

from .connection import KMIPServerMixin


class KMIPService(ConfigService, KMIPServerMixin):
    class Config:
        datastore = 'system_kmip'
        datastore_extend = 'kmip.kmip_extend'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.zfs_keys = {}
        self.datasets_datastore = 'storage.encrypteddataset'

    @private
    async def query_datasets(self, filters=None, options=None):
        return await self.middleware.call('datastore.query', self.datasets_datastore, filters or [], options or {})

    @private
    async def zfs_keys_pending_sync(self):
        config = await self.config()
        for ds in await self.middleware.call('datastore.query', self.datasets_datastore):
            if config['enabled'] and config['manage_zfs_keys'] and (
                ds['encryption_key'] or ds['name'] not in self.zfs_keys
            ):
                return True
            elif any(not config[k] for k in ('enabled', 'manage_zfs_keys')) and ds['kmip_uid']:
                return True
        return False

    @private
    def push_zfs_keys(self, ids=None):
        datasets = self.middleware.call_sync('kmip.query_datasets', [['id', 'in' if ids else 'nin', ids or []]])
        existing_datasets = {ds['name']: ds for ds in self.middleware.call_sync('pool.dataset.query')}
        failed = []
        with self._connection(self.middleware.call_sync('kmip.connection_config')) as conn:
            for ds in filter(lambda d: d['name'] in existing_datasets, datasets):
                if not ds['encryption_key']:
                    # We want to make sure we have the KMIP server's keys and in-memory keys in sync
                    try:
                        if ds['name'] in self.zfs_keys and self.middleware.call(
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

                self.zfs_keys[ds['name']] = self.middleware.call_sync('pwenc.decrypt', ds['encryption_key'])
                destroy_successful = False
                if ds['kmip_uid']:
                    # This needs to be revoked and destroyed
                    destroy_successful = self._revoke_and_destroy_key(ds['kmip_uid'], conn, self.middleware.logger)
                    if not destroy_successful:
                        self.middleware.logger.debug(f'Failed to destroy key from KMIP Server for {ds["name"]}')
                try:
                    uid = self._register_secret_data(self.zfs_keys[ds['name']], conn)
                except Exception:
                    failed.append(ds['name'])
                    update_data = {'kmip_uid': None} if destroy_successful else {}
                else:
                    update_data = {'encryption_key': None, 'kmip_uid': uid}
                if update_data:
                    self.middleware.call_sync('datastore.update', self.datasets_datastore, ds['id'], update_data)
        self.zfs_keys = {k: v for k, v in self.zfs_keys.items() if k in existing_datasets}
        return failed

    @private
    def pull_zfs_keys(self):
        datasets = self.middleware.call('kmip.query_datasets', [['kmip_uid', '!=', None]])
        existing_datasets = {ds['name']: ds for ds in self.middleware.call_sync('pool.dataset.query')}
        failed = []
        connection_successful = self.middleware.call_sync('kmip.test_connection')
        for ds in filter(lambda d: d['name'] in existing_datasets, datasets):
            try:
                if ds['name'] in self.zfs_keys and self.middleware.call_sync(
                    'zfs.dataset.check_key', ds['name'], {'key': self.zfs_keys[ds['name']]}
                ):
                    key = self.zfs_keys[ds['name']]
                elif connection_successful:
                    with self._connection(self.middleware.call_sync('kmip.connection_config')) as conn:
                        key = self._retrieve_secret_data(ds['kmip_uid'], conn)
                else:
                    continue
            except Exception:
                failed.append(ds['name'])
            else:
                update_data = {'encryption_key': self.middleware.call_sync('pwenc.encrypt', key), 'kmip_uid': None}
                self.middleware.call_sync('datastore.update', self.datasets_datastore, ds['id'], update_data)
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

    @private
    async def clear_sync_pending_zfs_keys(self):
        await self.middleware.call(
            'datastore.delete', self.datasets_datastore, [[
                'id', 'in', [ds['id'] for ds in await self.query_datasets([['kmip_uid', '!=', None]])]
            ]]
        )
        self.zfs_keys = {}

    @private
    def initialize_zfs_keys(self, connection_success):
        for ds in self.middleware.call_sync('kmip.query_datasets'):
            if ds['encryption_key']:
                self.zfs_keys[ds['name']] = self.middleware.call_sync('pwenc.decrypt', ds['encryption_key'])
            elif ds['kmip_uid'] and connection_success:
                try:
                    with self._connection(self.middleware.call_sync('kmip.connection_config')) as conn:
                        key = self._retrieve_secret_data(ds['kmip_uid'], conn)
                except Exception:
                    self.middleware.logger.debug(f'Failed to retrieve key for {ds["name"]}')
                else:
                    self.zfs_keys[ds['name']] = key

    @private
    async def retrieve_zfs_keys(self):
        return self.zfs_keys
