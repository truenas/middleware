import asyncio
import os

from middlewared.common.attachment import LockableFSAttachmentDelegate
from middlewared.schema import accepts, Bool, Dict, Int, Patch, Str, ValidationErrors
from middlewared.service import SharingService, SystemServiceService, private
import middlewared.sqlalchemy as sa


class WebDAVSharingModel(sa.Model):
    __tablename__ = 'sharing_webdav_share'

    id = sa.Column(sa.Integer(), primary_key=True)
    webdav_name = sa.Column(sa.String(120))
    webdav_comment = sa.Column(sa.String(120))
    webdav_path = sa.Column(sa.String(255))
    webdav_ro = sa.Column(sa.Boolean(), default=False)
    webdav_perm = sa.Column(sa.Boolean(), default=True)
    webdav_enabled = sa.Column(sa.Boolean(), default=True)


class WebDAVSharingService(SharingService):

    share_task_type = 'WebDAV'

    class Config:
        datastore = 'sharing.webdav_share'
        datastore_prefix = 'webdav_'
        namespace = 'sharing.webdav'
        cli_namespace = 'sharing.webdav'

    ENTRY = Patch(
        'webdav_share_create', 'webdav_share_entry',
        ('add', Bool('locked', required=True)),
        ('add', Int('id', required=True)),
        ('edit', {'name': 'comment', 'method': lambda x: setattr(x, 'required', True)}),
        ('edit', {'name': 'perm', 'method': lambda x: setattr(x, 'required', True)}),
        ('edit', {'name': 'ro', 'method': lambda x: setattr(x, 'required', True)}),
    )

    @private
    async def validate_data(self, data, schema):
        verrors = ValidationErrors()
        await self.validate_path_field(data, schema, verrors)

        if not data['name'].isalnum():
            verrors.add(
                f'{schema}.name',
                'Only alphanumeric characters are allowed'
            )

        verrors.check()

        if not os.path.exists(data[self.path_field]):
            os.makedirs(data[self.path_field])

    @accepts(
        Dict(
            'webdav_share_create',
            Bool('perm', default=True),
            Bool('ro', default=False),
            Str('comment'),
            Str('name', required=True, empty=False),
            Str('path', required=True, empty=False),
            Bool('enabled', default=True),
            register=True
        )
    )
    async def do_create(self, data):
        """
        Create a Webdav Share.

        `ro` when enabled prohibits users from writing to this share.

        `perm` when enabled automatically recursively changes the ownership of this share to
        webdav ( user and group both ).
        """

        await self.validate_data(data, 'webdav_share_create')

        data['id'] = await self.middleware.call(
            'datastore.insert',
            self._config.datastore,
            data,
            {'prefix': self._config.datastore_prefix}
        )
        if data['perm']:
            await self.middleware.call('filesystem.chown', {
                'path': data['path'],
                'uid': (await self.middleware.call('dscache.get_uncached_user', 'webdav'))['pw_uid'],
                'gid': (await self.middleware.call('dscache.get_uncached_group', 'webdav'))['gr_gid'],
                'options': {'recursive': True}
            })

        await self._service_change('webdav', 'reload')

        return await self.get_instance(data['id'])

    @accepts(
        Int('id', required=True),
        Patch('webdav_share_create', 'webdav_share_update', ('attr', {'update': True}))
    )
    async def do_update(self, id, data):
        """
        Update Webdav Share of `id`.
        """

        old = await self.query(filters=[('id', '=', id)], options={'get': True})
        new = old.copy()

        new.update(data)

        await self.validate_data(new, 'webdav_share_update')

        if len(set(old.items()) ^ set(new.items())) > 0:
            new.pop(self.locked_field)
            await self.middleware.call(
                'datastore.update',
                self._config.datastore,
                id,
                new,
                {'prefix': self._config.datastore_prefix}
            )

            await self._service_change('webdav', 'reload')

        if not old['perm'] and new['perm']:
            await self.middleware.call('filesystem.chown', {
                'path': new['path'],
                'uid': (await self.middleware.call('dscache.get_uncached_user', 'webdav'))['pw_uid'],
                'gid': (await self.middleware.call('dscache.get_uncached_group', 'webdav'))['gr_gid'],
                'options': {'recursive': True}
            })

        return await self.get_instance(id)

    async def do_delete(self, id):
        """
        Update Webdav Share of `id`.
        """

        response = await self.middleware.call(
            'datastore.delete',
            self._config.datastore,
            id
        )

        await self._service_change('webdav', 'reload')

        return response


class WebDAVModel(sa.Model):
    __tablename__ = 'services_webdav'

    id = sa.Column(sa.Integer(), primary_key=True)
    webdav_protocol = sa.Column(sa.String(120), default="http")
    webdav_tcpport = sa.Column(sa.Integer(), default=8080)
    webdav_tcpportssl = sa.Column(sa.Integer(), default=8081)
    webdav_password = sa.Column(sa.EncryptedText(), default='davtest')
    webdav_htauth = sa.Column(sa.String(120), default='digest')
    webdav_certssl_id = sa.Column(sa.ForeignKey('system_certificate.id'), nullable=True)


class WebDAVService(SystemServiceService):
    class Config:
        service = 'webdav'
        datastore_prefix = 'webdav_'
        datastore_extend = 'webdav.upper'
        cli_namespace = 'service.webdav'

    ENTRY = Dict(
        'webdav_entry',
        Str('protocol', enum=['HTTP', 'HTTPS', 'HTTPHTTPS'], required=True),
        Int('id', required=True),
        Int('tcpport', required=True),
        Int('tcpportssl', required=True),
        Str('password', required=True),
        Str('htauth', enum=['NONE', 'BASIC', 'DIGEST'], required=True),
        Int('certssl', null=True, required=True),
    )

    async def do_update(self, data):
        """
        Update Webdav Service Configuration.

        `protocol` specifies which protocol should be used for connecting to Webdav Serivce. Value of "HTTPHTTPS"
        allows both HTTP and HTTPS connections to the share.

        `certssl` is a valid id of a certificate configured in the system. This is required if HTTPS connection is
        desired with Webdave Service.

        There are 3 types of Authentication supported with Webdav:
        1) NONE      -   No authentication is required
        2) BASIC     -   Password is sent over the network as plaintext
        3) DIGEST    -   Hash of the password is sent over the network

        `htauth` should be one of the valid types described above.
        """
        old = await self.config()

        new = old.copy()
        new.update(data)

        await self.lower(new)
        await self.validate(new, 'webdav_update')
        await self._update_service(old, new)

        return await self.config()

    @private
    async def lower(self, data):
        data['protocol'] = data['protocol'].lower()
        data['htauth'] = data['htauth'].lower()

        return data

    @private
    async def upper(self, data):
        data['protocol'] = data['protocol'].upper()
        data['htauth'] = data['htauth'].upper()
        if data['certssl']:
            # FIXME: When we remove support for querying up foreign key objects in datastore, this should be fixed
            # to reflect that change
            data['certssl'] = data['certssl']['id']

        return data

    @private
    async def validate(self, data, schema_name):
        verrors = ValidationErrors()

        if data.get('protocol') == 'httphttps' and data.get('tcpport') == data.get('tcpportssl'):
            verrors.add(
                f"{schema_name}.tcpportssl",
                'The HTTP and HTTPS ports cannot be the same!'
            )

        cert_ssl = data.get('certssl') or 0
        if data.get('protocol') != 'http':
            if not cert_ssl:
                verrors.add(
                    f"{schema_name}.certssl",
                    'WebDAV SSL protocol specified without choosing a certificate'
                )
            else:
                verrors.extend((await self.middleware.call(
                    'certificate.cert_services_validation', cert_ssl, f'{schema_name}.certssl', False
                )))

        if verrors:
            raise verrors

        return data


async def pool_post_import(middleware, pool):
    """
    Makes sure to reload WebDAV if a pool is imported and there are shares configured for it.
    """
    if pool is None:
        asyncio.ensure_future(middleware.call('etc.generate', 'webdav'))
        return

    path = f'/mnt/{pool["name"]}'
    if await middleware.call('sharing.webdav.query', [
        ('OR', [
            ('path', '=', path),
            ('path', '^', f'{path}/'),
        ])
    ]):
        asyncio.ensure_future(middleware.call('service.reload', 'webdav'))


class WebDAVFSAttachmentDelegate(LockableFSAttachmentDelegate):
    name = 'webdav'
    title = 'WebDAV Share'
    service = 'webdav'
    service_class = WebDAVSharingService

    async def restart_reload_services(self, attachments):
        await self._service_change('webdav', 'reload')


async def setup(middleware):
    await middleware.call('pool.dataset.register_attachment_delegate', WebDAVFSAttachmentDelegate(middleware))
    middleware.register_hook('pool.post_import', pool_post_import, sync=True)
