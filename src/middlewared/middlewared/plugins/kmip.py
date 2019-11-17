from middlewared.service import (
    accepts, Bool, CallError, ConfigService, Dict, Int,
    job, List, private, Str, ValidationErrors
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
    def retrieve_zfs_keys_pending_sync(self, ids=None):
        return self.middleware.call_sync(
            'datastore.query', self.middleware.call_sync('pool.dataset.dataset_datastore'), [
                ['kmip_sync', '=', True], [['id', 'in' if ids else 'nin', ids or []]]
            ]
        )

    @private
    def sync_zfs_keys_from_db_to_server(self, ids=None):
        zfs_datastore = self.middleware.call_sync('pool.dataset.dataset_datastore')
        datasets = self.retrieve_zfs_keys_pending_sync(ids)
        failed = []
        with self.connection() as conn:
            for ds in datasets:
                self.zfs_keys[ds['name']] = ds['encryption_key']
                if ds['kmip_uid']:
                    # This needs to be revoked and destroyed
                    try:
                        self.revoke_key(ds['kmip_uid'], conn)
                    except Exception as e:
                        self.middleware.logger.debug(f'Failed to revoke old KMIP key for {ds["name"]}: {e}')
                    try:
                        self.destroy_key(ds['kmip_uid'], conn)
                    except Exception as e:
                        self.middleware.logger.debug(f'Failed to destroy old KMIP key for {ds["name"]}: {e}')

                try:
                    uid = self.__register_secret_data(
                        self.middleware.call_sync('pwenc.decrypt', ds['encryption_key']), conn
                    )
                except Exception as e:
                    failed.append((ds['name'], f'Failed to register key for {ds["name"]}: {e}'))
                else:
                    self.middleware.call_sync(
                        'datastore.update', zfs_datastore, ds['id'], {
                            'encryption_key': None, 'kmip_uid': uid, 'kmip_sync': False
                        }
                    )

        return failed

    @private
    def sync_zfs_keys_from_server_to_db(self, ids=None):
        zfs_datastore = self.middleware.call_sync('pool.dataset.dataset_datastore')
        datasets = self.retrieve_zfs_keys_pending_sync(ids)
        failed = []
        with self.connection() as conn:
            for ds in datasets:
                try:
                    key = self.__retrieve_secret_data(ds['kmip_uid'], conn)
                except Exception as e:
                    failed.append((ds['name'], f'Failed to retrieve key for {ds["name"]}: {e}'))
                else:
                    self.middleware.call_sync(
                        'datastore.update', zfs_datastore, ds['id'], {
                            'encryption_key': key, 'kmip_uid': None, 'kmip_sync': False
                        }
                    )

        return failed

    @private
    @accepts(List('ids', null=True, default=[]))
    @job(lock=lambda args: f'sync_zfs_keys_{args[0]}')
    def sync_zfs_keys(self, job, ids=None):
        config = self.middleware.call_sync('kmip.config')
        if self.test_connection()['error']:
            # TODO: Raise alert for connection failure
            return
        # TODO: Raise alerts for failed
        if config['enabled']:
            failed = self.sync_zfs_keys_from_db_to_server(ids)
        else:
            failed = self.sync_zfs_keys_from_server_to_db(ids)

    @private
    def register_secret_data(self, key, conn_data=None):
        with self.connection(conn_data) as conn:
            return self.__register_secret_data(key, conn)

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
    def revoke_and_destroy_key(self, uid, conn_data=None):
        with self.connection(conn_data) as conn:
            self.revoke_key(uid, conn)
            self.destroy_key(uid, conn)

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
            with self.connection(data) as conn:
                pass
        except Exception as e:
            return {'error': True, 'exception': str(e)}
        else:
            return {'error': False, 'exception': None}

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

        if new.pop('validate', True) and not verrors:
            result = await self.middleware.run_in_thread(self.test_connection, new)
            if result['error']:
                verrors.add('kmip_update.server', f'Unable to connect to KMIP server: {result["exception"]}.')

        verrors.check()

        await self.middleware.call(
            'datastore.update', self._config.datastore, old['id'], new,
        )

        await self.middleware.call('service.start', 'kmip')

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
    def initialize_keys(self):
        self.initialize_zfs_keys()

    @private
    async def retrieve_zfs_keys(self):
        return self.zfs_keys


async def __event_system(middleware, event_type, args):
    if args['id'] != 'ready':
        return

    if (await middleware.call('kmip.config'))['enabled']:
        await middleware.call('kmip.initialize_zfs_keys')


async def setup(middleware):
    middleware.event_subscribe('system', __event_system)
