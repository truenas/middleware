from middlewared.service import accepts, Bool, ConfigService, Dict, Int, private, Str, ValidationErrors
from middlewared.validators import Port

import middlewared.sqlalchemy as sa


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
            Bool('manage_sed_disks'),
            Bool('manage_zfs_keys'),
            Int('certificate', null=True),
            Int('certificate_authority', null=True),
            Int('port', validators=[Port()]),
            Str('server'),
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

        verrors.check()

        await self.middleware.call(
            'datastore.update', self._config.datastore, old['id'], new,
        )

        return await self.config()
