from middlewared.service import accepts, CallError, ConfigService, job, periodic, private

from .connection import KMIPServerMixin


class KMIPService(ConfigService, KMIPServerMixin):
    class Config:
        datastore = 'system_kmip'
        datastore_extend = 'kmip.kmip_extend'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.zfs_keys = {}

    @private
    def connection_config(self, data=None):
        config = self.middleware.call_sync('kmip.config')
        config.update(data or {})
        cert = self.middleware.call_sync('certificate.query', [['id', '=', config['certificate']]])
        ca = self.middleware.call_sync('certificateauthority.query', [['id', '=', config['certificate_authority']]])
        if not cert or not ca:
            raise CallError('Certificate/CA not setup correctly')
        return {
            **config, 'cert': cert[0]['certificate_path'],
            'cert_key': cert[0]['privatekey_path'], 'ca': ca[0]['certificate_path']
        }

    @private
    def test_connection(self, data=None, raise_alert=False):
        result = self._test_connection(self.connection_config(data))
        if result['error']:
            if raise_alert:
                config = self.middleware.call_sync('kmip.config')
                self.middleware.call_sync(
                    'alert.oneshot_create', 'KMIPConnectionFailed',
                    {'server': config['server'], 'error': result['exception']}
                )
            return False
        else:
            return True

    @private
    async def zfs_keys_pending_sync(self):
        config = await self.config()
        for ds in await self.middleware.call(
            'datastore.query', await self.middleware.call('pool.dataset.dataset_datastore')
        ):
            if config['enabled'] and config['manage_zfs_keys'] and ds['encryption_key']:
                return True
            elif any(not config[k] for k in ('enabled', 'manage_zfs_keys')) and ds['kmip_uid']:
                return True
        return False

    @private
    async def kmip_sync_pending(self):
        return await self.zfs_keys_pending_sync()

    @private
    def push_zfs_keys(self, ids=None):
        zfs_datastore = self.middleware.call_sync('pool.dataset.dataset_datastore')
        datasets = self.middleware.call_sync(
            'datastore.query', self.middleware.call_sync('pool.dataset.dataset_datastore'), [
                ['id', 'in' if ids else 'nin', ids or []]
            ]
        )
        existing_datasets = {ds['name']: ds for ds in self.middleware.call_sync('pool.dataset.query')}
        failed = []
        with self._connection(self.connection_config()) as conn:
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
                    destroy_successful = self._revoke_and_destroy_key(ds['kmip_uid'], conn)
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
                    self.middleware.call_sync('datastore.update', zfs_datastore, ds['id'], update_data)
        self.zfs_keys = {k: v for k, v in self.zfs_keys.items() if k in existing_datasets}
        return failed

    @private
    def pull_zfs_keys(self):
        zfs_datastore = self.middleware.call_sync('pool.dataset.dataset_datastore')
        datasets = self.middleware.call_sync(
            'datastore.query', self.middleware.call_sync('pool.dataset.dataset_datastore'), [['kmip_uid', '!=', None]]
        )
        existing_datasets = {ds['name']: ds for ds in self.middleware.call_sync('pool.dataset.query')}
        failed = []
        connection_successful = self.test_connection()
        for ds in filter(lambda d: d['name'] in existing_datasets, datasets):
            try:
                if ds['name'] in self.zfs_keys and self.middleware.call_sync(
                    'zfs.dataset.check_key', ds['name'], {'key': self.zfs_keys[ds['name']]}
                ):
                    key = self.zfs_keys[ds['name']]
                elif connection_successful:
                    with self._connection(self.connection_config()) as conn:
                        key = self._retrieve_secret_data(ds['kmip_uid'], conn)
                else:
                    continue
            except Exception:
                failed.append(ds['name'])
            else:
                update_data = {'encryption_key': self.middleware.call_sync('pwenc.encrypt', key), 'kmip_uid': None}
                self.middleware.call_sync('datastore.update', zfs_datastore, ds['id'], update_data)
                self.zfs_keys.pop(ds['name'], None)
                if connection_successful:
                    with self._connection(self.connection_config()) as conn:
                        self._revoke_and_destroy_key(ds['kmip_uid'], conn)
        self.zfs_keys = {k: v for k, v in self.zfs_keys.items() if k in existing_datasets}
        return failed

    @private
    @job(lock=lambda args: f'sync_zfs_keys_{args}')
    def sync_zfs_keys(self, job, ids=None):
        if not self.middleware.call_sync('kmip.zfs_keys_pending_sync'):
            return
        config = self.middleware.call_sync('kmip.config')
        conn_successful = self.test_connection(raise_alert=True)
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

    @periodic(interval=86400)
    @job()
    async def sync_keys(self, job):
        if not await self.middleware.call('kmip.kmip_sync_pending'):
            return
        await self.middleware.call('kmip.sync_zfs_keys')

    @private
    async def clear_sync_pending_zfs_keys(self):
        config = await self.config()
        zfs_datastore = await self.middleware.call('pool.dataset.dataset_datastore')
        clear_ids = [
            ds['id'] for ds in await self.middleware.call('datastore.query', zfs_datastore)
            if any(not config[k] for k in ('enabled', 'manage_zfs_keys')) and ds['kmip_uid']
        ]
        await self.middleware.call('datastore.delete', zfs_datastore, [['id', 'in', clear_ids]])

    @accepts()
    async def clear_sync_pending_keys(self):
        await self.clear_sync_pending_zfs_keys()

    @private
    def initialize_zfs_keys(self):
        connection_success = self.test_connection()
        for ds in self.middleware.call_sync(
            'datastore.query', self.middleware.call_sync('pool.dataset.dataset_datastore')
        ):
            if ds['encryption_key']:
                self.zfs_keys[ds['name']] = self.middleware.call_sync('pwenc.decrypt', ds['encryption_key'])
            elif ds['kmip_uid'] and connection_success:
                try:
                    with self._connection(self.connection_config()) as conn:
                        key = self._retrieve_secret_data(ds['kmip_uid'], conn)
                except Exception:
                    self.middleware.logger.debug(f'Failed to retrieve key for {ds["name"]}')
                else:
                    self.zfs_keys[ds['name']] = key

    @private
    @job(lock='initialize_kmip_keys')
    def initialize_keys(self, job):
        kmip_config = self.middleware.call_sync('kmip.config')
        if kmip_config['enabled'] and kmip_config['manage_zfs_keys']:
            self.initialize_zfs_keys()

    @private
    async def retrieve_zfs_keys(self):
        return self.zfs_keys
