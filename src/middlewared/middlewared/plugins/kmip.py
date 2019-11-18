from middlewared.service import (
    accepts, Bool, CallError, ConfigService, Dict, Int,
    job, List, periodic, private, Str, ValidationErrors
)
from middlewared.validators import Port

from kmip.core import enums
from kmip.pie.client import ProxyKmipClient
from kmip.pie.exceptions import ClientConnectionFailure, ClientConnectionNotOpen, KmipOperationFailure
from kmip.pie.objects import SecretData

import middlewared.sqlalchemy as sa

import contextlib
import socket


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.zfs_keys = {}

    @contextlib.contextmanager
    @private
    def connection(self, data=None):
        config = self.middleware.call_sync('kmip.config')
        config.update(data or {})
        cert = self.middleware.call_sync('certificate.query', [['id', '=', config['certificate']]])
        ca = self.middleware.call_sync('certificateauthority.query', [['id', '=', config['certificate_authority']]])
        if not cert or not ca:
            raise CallError('Certificate/CA not setup correctly')

        try:
            with ProxyKmipClient(
                hostname=config['server'], port=config['port'], cert=cert[0]['certificate_path'],
                key=cert[0]['privatekey_path'], ca=ca[0]['certificate_path']
            ) as conn:
                yield conn
        except (ClientConnectionFailure, ClientConnectionNotOpen, socket.timeout):
            raise CallError(f'Failed to connect to {config["server"]}:{config["port"]}')

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
    def sync_zfs_keys_from_db_to_server(self, ids=None):
        zfs_datastore = self.middleware.call_sync('pool.dataset.dataset_datastore')
        datasets = self.middleware.call_sync(
            'datastore.query', self.middleware.call_sync('pool.dataset.dataset_datastore'), [
                ['id', 'in' if ids else 'nin', ids or []]
            ]
        )
        existing_datasets = {ds['name']: ds for ds in self.middleware.call_sync('pool.dataset.query')}
        failed = []
        with self.connection() as conn:
            for ds in filter(lambda d: d['name'] in existing_datasets, datasets):
                if not ds['encryption_key']:
                    # We want to make sure we have the KMIP server's keys and in-memory keys in sync
                    try:
                        if ds['name'] in self.zfs_keys and self.middleware.call(
                            'zfs.dataset.check_key', ds['name'], {'key': self.zfs_keys[ds['name']]}
                        ):
                            continue
                        else:
                            key = self.__retrieve_secret_data(ds['kmip_uid'], conn)
                    except Exception as e:
                        self.middleware.logger.debug(f'Failed to retrieve key for {ds["name"]}: {e}')
                    else:
                        self.zfs_keys[ds['name']] = key
                        continue
                self.zfs_keys[ds['name']] = self.middleware.call_sync('pwenc.decrypt', ds['encryption_key'])
                destroy_successful = True
                if ds['kmip_uid']:
                    # This needs to be revoked and destroyed
                    destroy_successful = self.__revoke_and_destroy_key(ds, conn)
                try:
                    uid = self.__register_secret_data(self.zfs_keys[ds['name']], conn)
                except Exception:
                    failed.append(ds['name'])
                    update_data = {'kmip_uid': None} if destroy_successful else {}
                else:
                    update_data = {'encryption_key': None, 'kmip_uid': uid}
                if update_data:
                    self.middleware.call_sync('datastore.update', zfs_datastore, ds['id'], update_data)
        return failed

    @private
    def sync_zfs_keys_from_server_to_db(self, ids=None):
        zfs_datastore = self.middleware.call_sync('pool.dataset.dataset_datastore')
        datasets = self.middleware.call_sync(
            'datastore.query', self.middleware.call_sync('pool.dataset.dataset_datastore'), [
                ['kmip_uid', '!=', None], ['id', 'in' if ids else 'nin', ids or []]
            ]
        )
        existing_datasets = {ds['name']: ds for ds in self.middleware.call_sync('pool.dataset.query')}
        failed = []
        with self.connection() as conn:
            for ds in filter(lambda d: d['name'] in existing_datasets, datasets):
                try:
                    if ds['name'] in self.zfs_keys and self.middleware.call_sync(
                        'zfs.dataset.check_key', ds['name'], {'key': self.zfs_keys[ds['name']]}
                    ):
                        key = self.zfs_keys[ds['name']]
                    else:
                        key = self.__retrieve_secret_data(ds['kmip_uid'], conn)
                except Exception:
                    failed.append(ds['name'])
                else:
                    update_data = {'encryption_key': self.middleware.call_sync('pwenc.encrypt', key), 'kmip_uid': None}
                    self.middleware.call_sync('datastore.update', zfs_datastore, ds['id'], update_data)
                    self.zfs_keys.pop(ds['name'], None)
                    self.__revoke_and_destroy_key(ds, conn)
        self.zfs_keys = {k: v for k, v in self.zfs_keys.items() if k in existing_datasets}
        return failed

    @private
    @accepts(List('ids', null=True, default=[]))
    @job(lock=lambda args: f'sync_zfs_keys_{args}')
    def sync_zfs_keys(self, job, ids=None):
        config = self.middleware.call_sync('kmip.config')
        if not self.middleware.call_sync('kmip.kmip_sync_pending') or not self.test_connection_and_alert():
            return
        if config['enabled'] and config['manage_zfs_keys']:
            failed = self.sync_zfs_keys_from_db_to_server(ids)
        else:
            failed = self.sync_zfs_keys_from_server_to_db(ids)
        if failed:
            self.middleware.call_sync(
                'alert.oneshot_create', ' KMIPZFSDatasetsSyncFailure', {'datasets': ','.join(failed)}
            )

    @periodic(interval=86400)
    @job(lock='sync_kmip_keys')
    def sync_keys(self, job):
        if not self.middleware.call_sync('kmip.zfs_keys_pending_sync') or not self.test_connection_and_alert():
            return
        self.middleware.call_sync('kmip.sync_zfs_keys')

    @private
    def __revoke_and_destroy_key(self, ds, conn):
        try:
            self.revoke_key(ds['kmip_uid'], conn)
        except Exception as e:
            self.middleware.logger.debug(f'Failed to revoke old KMIP key for {ds["name"]}: {e}')
        try:
            self.destroy_key(ds['kmip_uid'], conn)
        except Exception as e:
            self.middleware.logger.debug(f'Failed to destroy old KMIP key for {ds["name"]}: {e}')
            return False
        else:
            return True

    @private
    def test_connection_and_alert(self):
        result = self.test_connection()
        if result['error']:
            config = self.middleware.call_sync('kmip.config')
            self.middleware.call_sync(
                'alert.oneshot_create', 'KMIPConnectionFailed',
                {'server': config['server'], 'error': result['exception']}
            )
            return False
        else:
            return True

    def __register_secret_data(self, key, conn):
        secret_data = SecretData(key.encode(), enums.SecretDataType.PASSWORD)
        try:
            uid = conn.register(secret_data)
        except KmipOperationFailure as e:
            raise CallError(f'Failed to register key with KMIP server: {e}')
        else:
            try:
                conn.activate(uid)
            except KmipOperationFailure as e:
                error = f'Failed to activate key: {e}'
                try:
                    self.destroy_key(uid, conn)
                except CallError as ce:
                    error += f'\nFailed to destroy created key: {ce}'
                raise CallError(error)
            return uid

    @private
    def revoke_key(self, uid, conn):
        try:
            conn.revoke(enums.RevocationReasonCode.CESSATION_OF_OPERATION, uid)
        except KmipOperationFailure as e:
            raise CallError(f'Failed to revoke key: {e}')

    @private
    def destroy_key(self, uid, conn):
        try:
            conn.destroy(uid)
        except KmipOperationFailure as e:
            raise CallError(f'Failed to destroy key: {e}')

    @private
    @accepts(Str('uid'), Dict('conn_data', additional_attrs=True))
    def retrieve_secret_data(self, uid, conn_data=None):
        with self.connection(conn_data) as conn:
            return self.__retrieve_secret_data(uid, conn)

    def __retrieve_secret_data(self, uid, conn):
        try:
            obj = conn.get(uid)
        except KmipOperationFailure as e:
            raise CallError(f'Failed to retrieve secret data: {e}')
        else:
            if not isinstance(obj, SecretData):
                raise CallError('Retrieved managed object is not secret data')
            return obj.value.decode()

    @private
    def test_connection(self, data=None):
        try:
            with self.connection(data):
                pass
        except Exception as e:
            return {'error': True, 'exception': str(e)}
        else:
            return {'error': False, 'exception': None}

    @private
    async def kmip_sync_pending(self):
        return await self.zfs_keys_pending_sync()

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
    async def kmip_extend(self, data):
        for k in filter(lambda v: data[v], ('certificate', 'certificate_authority')):
            data[k] = data[k]['id']
        return data

    @accepts(
        Dict(
            'kmip_update',
            Bool('enabled'),
            Bool('manage_sed_disks'),
            Bool('manage_zfs_keys'),
            Bool('validate'),
            Int('certificate', null=True),
            Int('certificate_authority', null=True),
            Int('port', validators=[Port()]),
            Str('server'),
            update=True
        )
    )
    async def do_update(self, data):
        old = await self.config()
        new = old.copy()
        new.update(data)
        verrors = ValidationErrors()

        if not new['server']:
            verrors.add('kmip_update.server', 'Please specify a valid hostname or an IPv4 address')

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
        elif not ca:
            verrors.add('kmip_update.certificate_authority', 'Please specify a valid id.')

        if new.pop('validate', True) and new['enabled'] and not verrors:
            result = await self.middleware.run_in_thread(self.test_connection, new)
            if result['error']:
                verrors.add('kmip_update.server', f'Unable to connect to KMIP server: {result["exception"]}.')

        sync_error = 'KMIP sync is pending, please make sure database and KMIP server ' \
                     'are in sync before proceeding with this operation.'
        if old['enabled'] != new['enabled'] and await self.kmip_sync_pending():
            verrors.add('kmip_update.enabled', sync_error)
        elif old['manage_zfs_keys'] != new['manage_zfs_keys'] and await self.zfs_keys_pending_sync():
            verrors.add('kmip_update.manage_zfs_keys', sync_error)

        verrors.check()

        await self.middleware.call(
            'datastore.update', self._config.datastore, old['id'], new,
        )

        await self.middleware.call('service.start', 'kmip')
        if new['enabled'] and old['enabled'] != new['enabled']:
            await self.middleware.call('kmip.initialize_keys')
        if any(old[k] != new[k] for k in ('enabled', 'manage_zfs_keys', 'manage_sed_keys')):
            await self.middleware.call('kmip.sync_keys')

        return await self.config()

    @private
    def initialize_zfs_keys(self):
        for ds in self.middleware.call_sync(
            'datastore.query', self.middleware.call_sync('pool.dataset.dataset_datastore')
        ):
            if ds['encryption_key']:
                self.zfs_keys[ds['name']] = self.middleware.call_sync('pwenc.decrypt', ds['encryption_key'])
            elif ds['kmip_uid']:
                try:
                    key = self.retrieve_secret_data(ds['kmip_uid'])
                except Exception:
                    self.middleware.logger.debug(f'Failed to retrieve key for {ds["name"]}')
                else:
                    self.zfs_keys[ds['name']] = key

    @private
    @job(lock='initialize_kmip_keys')
    def initialize_keys(self, job):
        kmip_config = self.middleware.call_sync('kmip.config')
        if kmip_config['manage_zfs_keys']:
            self.initialize_zfs_keys()

    @private
    async def retrieve_zfs_keys(self):
        return self.zfs_keys


async def __event_system(middleware, event_type, args):
    if args['id'] != 'ready':
        return

    if (await middleware.call('kmip.config'))['enabled']:
        await middleware.call('kmip.initialize_keys')


async def setup(middleware):
    middleware.event_subscribe('system', __event_system)
    if await middleware.call('system.ready'):
        await middleware.call('kmip.initialize_keys')
