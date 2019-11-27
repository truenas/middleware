import middlewared.sqlalchemy as sa

from middlewared.service import accepts, CallError, ConfigService, job, private, ValidationErrors
from middlewared.schema import Bool, Dict, Int, Str
from middlewared.validators import Port


class KMIPModel(sa.Model):
    __tablename__ = 'system_kmip'

    id = sa.Column(sa.Integer(), primary_key=True)
    server = sa.Column(sa.String(128), default=None, nullable=True)
    port = sa.Column(sa.SmallInteger(), default=5696)
    certificate_id = sa.Column(sa.ForeignKey('system_certificate.id'), index=True, nullable=True)
    certificate_authority_id = sa.Column(sa.ForeignKey('system_certificateauthority.id'), index=True, nullable=True)
    manage_sed_disks = sa.Column(sa.Boolean(), default=False)
    manage_zfs_keys = sa.Column(sa.Boolean(), default=False)
    enabled = sa.Column(sa.Boolean(), default=False)


class KMIPService(ConfigService):
    class Config:
        datastore = 'system_kmip'
        datastore_extend = 'kmip.kmip_extend'

    @private
    async def kmip_extend(self, data):
        for k in filter(lambda v: data[v], ('certificate', 'certificate_authority')):
            data[k] = data[k]['id']
        return data

    @accepts(
        Dict(
            'kmip_update',
            Bool('enabled'),
            Bool('force_clear'),
            Bool('manage_sed_disks'),
            Bool('manage_zfs_keys'),
            Bool('change_server'),
            Bool('validate'),
            Int('certificate', null=True),
            Int('certificate_authority', null=True),
            Int('port', validators=[Port()]),
            Str('server'),
            update=True
        )
    )
    @job(lock='kmip_update')
    async def do_update(self, job, data):
        """
        Update KMIP Server Configuration.

        System currently authenticates connection with remote KMIP Server with a TLS handshake. `certificate` and
        `certificate_authority` determine the certs which will be used to initiate the TLS handshake with `server`.

        `validate` is enabled by default. When enabled, system will test connection to `server` making sure
        it's reachable.

        `manage_zfs_keys`/`manage_sed_disks` when enabled will sync keys from local database to remote KMIP server.
        When disabled, if there are any keys left to be retrieved from the KMIP server,
        it will sync them back to local database.

        `enabled` if true, cannot be set to disabled if there are existing keys pending to be synced. However users
        can still perform this action by enabling `force_clear`.

        `change_server` is a boolean field which allows users to migrate data between two KMIP servers. System
        will first migrate keys from old KMIP server to local database and then migrate the keys from local database
        to new KMIP server. If it is unable to retrieve all the keys from old server, this will fail. Users can bypass
        this by enabling `force_clear`.

        `force_clear` is a boolean option which when enabled will in this case remove all
        pending keys to be synced from database. It should be used with extreme caution as users may end up with
        not having ZFS dataset or SED disks keys leaving them locked forever. It is disabled by default.
        """
        old = await self.config()
        new = old.copy()
        new.update(data)
        verrors = ValidationErrors()

        if not new['server'] and new['enabled']:
            verrors.add('kmip_update.server', 'Please specify a valid hostname or an IPv4 address')

        if new['enabled']:
            verrors.extend((await self.middleware.call(
                'certificate.cert_services_validation', new['certificate'], 'kmip_update.certificate', False
            )))

        ca = await self.middleware.call('certificateauthority.query', [['id', '=', new['certificate_authority']]])
        if ca and not verrors:
            ca = ca[0]
            if not await self.middleware.call(
                'cryptokey.validate_cert_with_chain',
                (await self.middleware.call('certificate._get_instance', new['certificate']))['certificate'],
                [ca['certificate']]
            ):
                verrors.add(
                    'kmip_update.certificate_authority',
                    'Certificate chain could not be verified with specified certificate authority.'
                )
        elif not ca and new['enabled']:
            verrors.add('kmip_update.certificate_authority', 'Please specify a valid id.')

        if new.pop('validate', True) and new['enabled'] and not verrors:
            if not await self.middleware.call('kmip.test_connection', new):
                verrors.add('kmip_update.server', f'Unable to connect to {new["server"]}:{new["port"]} KMIP server.')

        change_server = new.pop('change_server', False)
        if change_server and new['server'] == old['server']:
            verrors.add('kmip_update.change_server', 'Please update server field to reflect the new server.')
        if change_server and not new['enabled']:
            verrors.add('kmip_update.enabled', 'Must be enabled when change server is enabled.')

        force_clear = new.pop('force_clear', False)
        clear_keys = force_clear if change_server else False
        sync_error = 'KMIP sync is pending, please make sure database and KMIP server ' \
                     'are in sync before proceeding with this operation.'
        if old['enabled'] != new['enabled'] and await self.middleware.call('kmip.kmip_sync_pending'):
            if force_clear:
                clear_keys = True
            else:
                verrors.add('kmip_update.enabled', sync_error)

        verrors.check()

        job.set_progress(30, 'Initial Validation complete')

        if clear_keys:
            await self.middleware.call('kmip.clear_sync_pending_keys')
            job.set_progress(50, 'Cleared keys pending sync')

        if change_server:
            # We will first migrate all the keys to local database - once done with that,
            # we will proceed with pushing it to the new server - we should have the old server
            # old server -> db
            # db -> new server
            # First can be skipped if old server is not reachable and we want to clear keys
            job.set_progress(55, 'Starting migration from existing server to new server')
            await self.middleware.call(
                'datastore.update', self._config.datastore, old['id'], {
                    'manage_zfs_keys': False, 'manage_sed_disks': False
                }
            )
            job.set_progress(60, 'Syncing keys from existing server to local database')
            sync_jobs = [
                (await self.middleware.call(f'kmip.{i}', True)) for i in ('sync_zfs_keys', 'sync_sed_keys')
            ]
            errors = []
            for sync_job in sync_jobs:
                await sync_job.wait()
                if sync_job.error:
                    errors.append(sync_job.error)
                elif sync_job.result:
                    errors.append(f'Failed to sync {",".join(sync_job.result)}')

            if errors:
                await self.middleware.call('datastore.update', self._config.datastore, old['id'], old)
                # We do this because it's possible a few datasets/disks got synced to db and few didn't - this is
                # to push all the data of interest back to the KMIP server from db
                await self.middleware.call('kmip.sync_keys')
                errors = '\n'.join(errors)
                raise CallError(f'Failed to sync keys from {old["server"]} to host: {errors}')

            if await self.middleware.call('kmip.kmip_sync_pending'):
                raise CallError(sync_error)

            job.set_progress(80, 'Successfully synced keys from existing server to local database')

        await self.middleware.call(
            'datastore.update', self._config.datastore, old['id'], new,
        )

        await self.middleware.call('service.start', 'kmip')
        if new['enabled'] and old['enabled'] != new['enabled']:
            await self.middleware.call('kmip.initialize_keys')
        if any(old[k] != new[k] for k in ('enabled', 'manage_zfs_keys', 'manage_sed_disks')) or change_server:
            job.set_progress(90, 'Starting sync between local database and configured KMIP server')
            await self.middleware.call('kmip.sync_keys')

        return await self.config()
