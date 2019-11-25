from middlewared.service import accepts, CallError, ConfigService, job, periodic, private

from .connection import KMIPServerMixin


class KMIPService(ConfigService, KMIPServerMixin):
    class Config:
        datastore = 'system_kmip'
        datastore_extend = 'kmip.kmip_extend'

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
    async def kmip_sync_pending(self):
        return await self.middleware.call('kmip.zfs_keys_pending_sync') or await self.middleware.call(
            'kmip.sed_keys_pending_sync'
        )

    @periodic(interval=86400)
    async def sync_keys(self):
        if not await self.middleware.call('kmip.kmip_sync_pending'):
            return
        await self.middleware.call('kmip.sync_zfs_keys')
        await self.middleware.call('kmip.sync_sed_keys')

    @accepts()
    async def clear_sync_pending_keys(self):
        config = await self.config()
        clear = not config['enabled']
        if clear or not config['manage_zfs_keys']:
            await self.middleware.call('kmip.clear_sync_pending_zfs_keys')
        if clear or not config['manage_sed_disks']:
            await self.middleware.call('kmip.clear_sync_pending_sed_keys')

    @private
    def delete_kmip_secret_data(self, uid):
        with self._connection(self.connection_config()) as conn:
            return self._revoke_and_destroy_key(uid, conn, self.middleware.logger)

    @private
    @job(lock='initialize_kmip_keys')
    async def initialize_keys(self, job):
        kmip_config = await self.config()
        if kmip_config['enabled']:
            connection_success = await self.middleware.call('kmip.test_connection')
            if kmip_config['manage_zfs_keys']:
                await self.middleware.call('kmip.initialize_zfs_keys', connection_success)
            if kmip_config['manage_sed_disks']:
                await self.middleware.call('kmip.initialize_sed_keys', connection_success)
