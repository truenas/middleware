from middlewared.service import accepts, CallError, ConfigService, job, periodic, private

from .connection import KMIPServerMixin


class KMIPService(ConfigService, KMIPServerMixin):
    class Config:
        datastore = 'system_kmip'
        datastore_extend = 'kmip.kmip_extend'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.zfs_keys = {}
        self.disks_keys = {}
        self.global_sed_key = ''

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
        for ds in await self.middleware.call('datastore.query', 'storage.encrypteddataset'):
            if config['enabled'] and config['manage_zfs_keys'] and ds['encryption_key']:
                return True
            elif any(not config[k] for k in ('enabled', 'manage_zfs_keys')) and ds['kmip_uid']:
                return True
        return False

    @private
    async def sed_keys_pending_sync(self):
        adv_config = await self.middleware.call('system.advanced.config')
        disks = await self.middleware.call('disk.query')
        config = await self.config()
        check_kmip_uid = any(not config[k] for k in ('enabled', 'manage_zfs_keys'))
        check_db_key = config['enabled'] and config['manage_sed_disks']
        for disk in disks:
            if check_db_key and disk['passwd']:
                return True
            elif check_kmip_uid and disk['kmip_uid']:
                return True
        if check_db_key and adv_config['sed_passwd']:
            return True
        elif check_kmip_uid and adv_config['kmip_uid']:
            return True
        return False

    @private
    async def kmip_sync_pending(self):
        return await self.zfs_keys_pending_sync() or await self.sed_keys_pending_sync()

    @private
    def push_zfs_keys(self, ids=None):
        datasets = self.middleware.call_sync(
            'datastore.query', 'storage.encrypteddataset', [['id', 'in' if ids else 'nin', ids or []]]
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
                    self.middleware.call_sync('datastore.update', 'storage.encrypteddataset', ds['id'], update_data)
        self.zfs_keys = {k: v for k, v in self.zfs_keys.items() if k in existing_datasets}
        return failed

    @private
    def pull_zfs_keys(self):
        datasets = self.middleware.call_sync('datastore.query', 'storage.encrypteddataset', [['kmip_uid', '!=', None]])
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
                self.middleware.call_sync('datastore.update', 'storage.encrypteddataset', ds['id'], update_data)
                self.zfs_keys.pop(ds['name'], None)
                if connection_successful:
                    with self._connection(self.connection_config()) as conn:
                        self._revoke_and_destroy_key(ds['kmip_uid'], conn)
        self.zfs_keys = {k: v for k, v in self.zfs_keys.items() if k in existing_datasets}
        return failed

    @private
    @job(lock=lambda args: f'kmip_sync_zfs_keys_{args}')
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
    async def sync_keys(self):
        if not await self.middleware.call('kmip.kmip_sync_pending'):
            return
        await self.middleware.call('kmip.sync_zfs_keys')
        await self.middleware.call('kmip.sync_sed_keys')

    @private
    def push_sed_keys(self, ids=None):
        adv_config = self.middleware.call_sync('system.advanced.config')
        failed = []
        with self._connection(self.connection_config()) as conn:
            for disk in self.middleware.call_sync('disk.query', [['id', 'in' if ids else 'nin', ids or []]]):
                if not disk['passwd'] and disk['kmip_uid']:
                    try:
                        key = self._retrieve_secret_data(disk['kmip_uid'], conn)
                    except Exception as e:
                        self.middleware.logger.debug(f'Failed to retrieve key for {disk["identifier"]}: {e}')
                    else:
                        self.disks_keys[disk['identifier']] = key
                    continue
                elif not disk['passwd']:
                    continue

                self.disks_keys[disk['identifier']] = disk['passwd']
                destroy_successful = False
                if disk['kmip_uid']:
                    # This needs to be revoked and destroyed
                    destroy_successful = self._revoke_and_destroy_key(disk['kmip_uid'], conn)
                    if not destroy_successful:
                        self.middleware.logger.debug(f'Failed to destroy key from KMIP Server for {disk["identifier"]}')
                try:
                    uid = self._register_secret_data(self.disks_keys[disk['identifier']], conn)
                except Exception:
                    failed.append(disk['identifier'])
                    update_data = {'kmip_uid': None} if destroy_successful else {}
                else:
                    update_data = {'passwd': '', 'kmip_uid': uid}
                if update_data:
                    self.middleware.call_sync(
                        'datastore.update', 'storage.disk', disk['id'], update_data, {'prefix': 'disk_'}
                    )
            if not adv_config['sed_passwd'] and adv_config['kmip_uid']:
                try:
                    key = self._retrieve_secret_data(adv_config['kmip_uid'], conn)
                except Exception:
                    failed.append('Global SED Key')
                else:
                    self.global_sed_key = key
            elif adv_config['sed_passwd'] and not adv_config['kmip_uid']:
                self.global_sed_key = adv_config['sed_passwd']
                try:
                    uid = self._register_secret_data(self.global_sed_key, conn)
                except Exception:
                    failed.append('Global SED Key')
                else:
                    self.middleware.call_sync(
                        'datastore.update', 'system.advanced',
                        adv_config['id'], {'adv_sed_passwd': '', 'adv_kmip_uid': uid}
                    )
        return failed

    @private
    def pull_sed_keys(self):
        failed = []
        connection_successful = self.test_connection()
        for disk in self.middleware.call_sync('disk.query', [['kmip_uid', '!=', None]]):
            try:
                if self.disks_keys.get(disk['identifier']):
                    key = self.disks_keys[disk['identifier']]
                elif connection_successful:
                    with self._connection(self.connection_config()) as conn:
                        key = self._retrieve_secret_data(disk['kmip_uid'], conn)
                else:
                    continue
            except Exception:
                failed.append(disk['identifier'])
            else:
                update_data = {'passwd': self.middleware.call_sync('pwenc.encrypt', key), 'kmip_uid': None}
                self.middleware.call_sync(
                    'datastore.update', 'storage.disk', disk['id'], update_data, {'prefix': 'disk_'}
                )
                self.disks_keys.pop(disk['identifier'], None)
                if connection_successful:
                    with self._connection(self.connection_config()) as conn:
                        self._revoke_and_destroy_key(disk['kmip_uid'], conn)
        adv_config = self.middleware.call_sync('system.advanced.config')
        if adv_config['kmip_uid']:
            key = None
            if self.global_sed_key:
                key = self.global_sed_key
            elif connection_successful:
                try:
                    with self._connection(self.connection_config()) as conn:
                        key = self._retrieve_secret_data(adv_config['kmip_uid'], conn)
                except Exception:
                    failed.append('Global SED Key')
            if key:
                # TODO: Validate need of encrypting/decrypted global sed password
                self.middleware.call_sync(
                    'datastore.update', 'system.advanced',
                    adv_config['id'], {'adv_sed_passwd': key, 'adv_kmip_uid': None}
                )
                if connection_successful:
                    with self._connection(self.connection_config()) as conn:
                        self._revoke_and_destroy_key(adv_config['kmip_uid'], conn)
        return failed

    @job(lock=lambda args: f'kmip_sync_sed_keys_{args}')
    def sync_sed_keys(self, job, ids=None):
        if not self.middleware.call_sync('kmip.sed_keys_pending_sync'):
            return
        config = self.middleware.call_sync('kmip.config')
        conn_successful = self.test_connection(raise_alert=True)
        if config['enabled'] and config['manage_sed_disks']:
            if conn_successful:
                failed = self.push_sed_keys(ids)
            else:
                return
        else:
            failed = self.pull_sed_keys()
        # TODO: Raise disk alerts

    @private
    async def clear_sync_pending_zfs_keys(self):
        config = await self.config()
        clear_ids = [
            ds['id'] for ds in await self.middleware.call('datastore.query', 'storage.encrypteddataset')
            if any(not config[k] for k in ('enabled', 'manage_zfs_keys')) and ds['kmip_uid']
        ]
        await self.middleware.call('datastore.delete', 'storage.encrypteddataset', [['id', 'in', clear_ids]])

    @accepts()
    async def clear_sync_pending_keys(self):
        await self.clear_sync_pending_zfs_keys()

    @private
    def initialize_zfs_keys(self, connection_success):
        for ds in self.middleware.call_sync('datastore.query', 'storage.encrypteddataset'):
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
    def initialize_sed_keys(self, connection_success):
        for disk in self.middleware.call_sync('disk.query'):
            if disk['passwd']:
                self.disks_keys[disk['identifier']] = disk['passwd']
            elif disk['kmip_uid'] and connection_success:
                try:
                    with self._connection(self.connection_config()) as conn:
                        key = self._retrieve_secret_data(disk['kmip_uid'], conn)
                except Exception:
                    self.middleware.logger.debug(f'Failed to retrieve SED disk key for {disk["identifier"]}')
                else:
                    self.disks_keys[disk['identifier']] = key
        adv_config = self.middleware.call_sync('system.advanced.config')
        if adv_config['sed_passwd']:
            self.global_sed_key = adv_config['sed_passwd']
        elif connection_success and adv_config['kmip_uid']:
            try:
                with self._connection(self.connection_config()) as conn:
                    key = self._retrieve_secret_data(adv_config['kmip_uid'], conn)
            except Exception:
                self.middleware.logger.debug(f'Failed to retrieve global SED key')
            else:
                self.global_sed_key = key

    @private
    @job(lock='initialize_kmip_keys')
    def initialize_keys(self, job):
        kmip_config = self.middleware.call_sync('kmip.config')
        if kmip_config['enabled']:
            connection_success = self.test_connection()
            if kmip_config['manage_zfs_keys']:
                self.initialize_zfs_keys(connection_success)
            if kmip_config['manage_sed_disks']:
                self.initialize_sed_keys(connection_success)

    @private
    async def retrieve_zfs_keys(self):
        return self.zfs_keys

    @private
    async def sed_global_password(self):
        return self.global_sed_key

    @private
    async def retrieve_sed_disks_keys(self):
        return self.disks_keys
