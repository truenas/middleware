from middlewared.async_validators import check_path_resides_within_volume
from middlewared.common.listen import SystemServiceListenSingleDelegate
from middlewared.schema import accepts, Bool, Dict, Int, Patch, returns, Str
from middlewared.validators import Match, Range
from middlewared.service import SystemServiceService, ValidationErrors, private
import middlewared.sqlalchemy as sa


import os


class S3Model(sa.Model):
    __tablename__ = 'services_s3'

    id = sa.Column(sa.Integer(), primary_key=True)
    s3_bindip = sa.Column(sa.String(128))
    s3_bindport = sa.Column(sa.SmallInteger(), default=9000)
    s3_access_key = sa.Column(sa.String(128), default='')
    s3_secret_key = sa.Column(sa.EncryptedText(), default='')
    s3_mode = sa.Column(sa.String(120), default="local")
    s3_disks = sa.Column(sa.String(255), default='')
    s3_certificate_id = sa.Column(sa.ForeignKey('system_certificate.id'), index=True, nullable=True)
    s3_browser = sa.Column(sa.Boolean(), default=True)


class S3Service(SystemServiceService):

    class Config:
        service = "s3"
        datastore_prefix = "s3_"
        datastore_extend = "s3.config_extend"
        cli_namespace = "service.s3"

    ENTRY = Dict(
        's3_entry',
        Str('bindip', required=True),
        Int('bindport', validators=[Range(min=1, max=65535)], required=True),
        Str('access_key', max_length=20, required=True),
        Str('secret_key', max_length=40, required=True),
        Bool('browser', required=True),
        Str('storage_path', required=True),
        Int('certificate', null=True, required=True),
        Int('id', required=True),
    )

    @accepts()
    @returns(Dict('s3_bindip_choices', additional_attrs=True))
    async def bindip_choices(self):
        """
        Return ip choices for S3 service to use.
        """
        return {
            d['address']: d['address'] for d in await self.middleware.call(
                'interface.ip_in_use', {'static': True, 'any': True}
            )
        }

    @private
    async def config_extend(self, s3):
        s3['storage_path'] = s3.pop('disks', None)
        s3.pop('mode', None)
        if s3.get('certificate'):
            s3['certificate'] = s3['certificate']['id']
        return s3

    @accepts(Patch(
        's3_entry', 's3_update',
        ('edit', {'name': 'access_key', 'method': lambda x: setattr(
            x, 'validators', [Match(r'^\w+$', explanation='Should only contain alphanumeric characters')]
        )}),
        ('edit', {'name': 'secret_key', 'method': lambda x: setattr(
            x, 'validators', [Match(r'^\w+$', explanation='Should only contain alphanumeric characters')]
        )}),
        ('rm', {'name': 'id'}),
        ('attr', {'update': True}),
    ))
    async def do_update(self, data):
        """
        Update S3 Service Configuration.

        `access_key` must only contain alphanumeric characters and should be between 5 and 20 characters.

        `secret_key` must only contain alphanumeric characters and should be between 8 and 40 characters.

        `browser` when set, enables the web user interface for the S3 Service.

        `certificate` is a valid certificate id which exists in the system. This is used to enable secure
        S3 connections.
        """
        old = await self.config()

        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()

        for attr, minlen, maxlen in (
            ('access_key', 5, 20),
            ('secret_key', 8, 40),
        ):
            curlen = len(new.get(attr, ''))
            if curlen < minlen or curlen > maxlen:
                verrors.add(
                    f's3_update.{attr}', f'Attribute should be {minlen} to {maxlen} in length'
                )

        if not new['storage_path'] and await self.middleware.call('service.started', 's3'):
            verrors.add('s3_update.storage_path', 'S3 must be stopped before unsetting storage path.')
        elif new['storage_path']:
            await check_path_resides_within_volume(
                verrors, self.middleware, 's3_update.storage_path', new['storage_path']
            )

            if not verrors:
                if new['storage_path'].rstrip('/').count('/') < 3:
                    verrors.add(
                        's3_update.storage_path',
                        'Top level datasets are not allowed. i.e /mnt/tank/dataset is allowed'
                    )
                else:
                    # If the storage_path does not exist, let's create it
                    if not os.path.exists(new['storage_path']):
                        os.makedirs(new['storage_path'])

        if new['certificate']:
            verrors.extend((await self.middleware.call(
                'certificate.cert_services_validation', new['certificate'], 's3_update.certificate', False
            )))

        if new['bindip'] not in await self.bindip_choices():
            verrors.add('s3_update.bindip', 'Please provide a valid ip address')

        if verrors:
            raise verrors

        new['disks'] = new.pop('storage_path')

        await self._update_service(old, new)

        if new['disks'] and (await self.middleware.call('filesystem.stat', new['disks']))['user'] != 'minio':
            await self.middleware.call(
                'filesystem.setperm',
                {
                    'path': new['disks'],
                    'mode': str(775),
                    'uid': (await self.middleware.call('dscache.get_uncached_user', 'minio'))['pw_uid'],
                    'gid': (await self.middleware.call('dscache.get_uncached_group', 'minio'))['gr_gid'],
                    'options': {'recursive': True, 'traverse': False}
                }
            )

        return await self.config()


async def setup(middleware):
    await middleware.call(
        'interface.register_listen_delegate',
        SystemServiceListenSingleDelegate(middleware, 's3', 'bindip'),
    )
