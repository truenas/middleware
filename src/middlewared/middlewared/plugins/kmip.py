from middlewared.service import (
    accepts, Bool, CallError, ConfigService, Dict, Int, private, Str, ValidationErrors
)
from middlewared.validators import Port

from kmip.pie.client import ProxyKmipClient

import middlewared.sqlalchemy as sa

import contextlib


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

    @contextlib.contextmanager
    def connection(self, data=None):
        config = self.middleware.call_sync('kmip.config')
        config.update(data or {})
        cert = self.middleware.call_sync('certificate.query', [['id', '=', config['certificate']]])
        ca = self.middleware.call_sync('certificateauthority.query', [['id', '=', config['certificate_authority']]])
        if not cert or not ca:
            raise CallError('Certificate/CA not setup correctly')

        with ProxyKmipClient(
            hostname=config['server'], port=config['port'], cert=cert[0]['certificate_path'],
            key=cert[0]['privatekey_path'], ca=ca[0]['certificate_path']
        ) as conn:
            yield conn

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
