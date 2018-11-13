from middlewared.async_validators import check_path_resides_within_volume
from middlewared.schema import accepts, Bool, Dict, Int, Patch, Str, ValidationErrors
from middlewared.service import CRUDService, SystemServiceService, private


class WebDAVSharingService(CRUDService):

    class Config:
        datastore = 'sharing.webdav_share'
        datastore_prefix = 'webdav_'
        namespace = 'sharing.webdav'

    @private
    async def validate_data(self, data, schema):
        verrors = ValidationErrors()

        path = data.get('path')
        if not path:
            verrors.add(
                f'{schema}.path',
                'This field is required'
            )
        else:
            await check_path_resides_within_volume(verrors, self.middleware, f'{schema}.path', data['path'])

        name = data.get('name')
        if not name:
            verrors.add(
                f'{schema}.name',
                'This field is required'
            )
        else:
            if not name.isalnum():
                verrors.add(
                    f'{schema}.name',
                    'Only AlphaNumeric characters are allowed'
                )

        if verrors:
            raise verrors

    @accepts(
        Dict(
            'webdav_share_create',
            Bool('perm', default=True),
            Bool('ro', default=False),
            Str('comment'),
            Str('name', required=True),
            Str('path', required=True),
            register=True
        )
    )
    async def do_create(self, data):

        await self.validate_data(data, 'webdav_share_create')

        data['id'] = await self.middleware.call(
            'datastore.insert',
            self._config.datastore,
            data,
            {'prefix': self._config.datastore_prefix}
        )

        await self._service_change('webdav', 'reload')

        return await self.query(filters=[('id', '=', data['id'])], options={'get': True})

    @accepts(
        Int('id', required=True),
        Patch('webdav_share_create', 'webdav_share_update', ('attr', {'update': True}))
    )
    async def do_update(self, id, data):

        old = await self.query(filters=[('id', '=', id)], options={'get': True})
        new = old.copy()

        new.update(data)

        await self.validate_data(new, 'webdav_share_update')

        if len(set(old.items()) ^ set(new.items())) > 0:

            await self.middleware.call(
                'datastore.update',
                self._config.datastore,
                id,
                new,
                {'prefix': self._config.datastore_prefix}
            )

            await self._service_change('webdav', 'reload')

        return await self.query(filters=[('id', '=', id)], options={'get': True})

    @accepts(
        Int('id')
    )
    async def do_delete(self, id):

        response = await self.middleware.call(
            'datastore.delete',
            self._config.datastore,
            id
        )

        await self._service_change('webdav', 'reload')

        return response


class WebDAVService(SystemServiceService):
    class Config:
        service = 'webdav'
        datastore_prefix = 'webdav_'
        datastore_extend = 'webdav.upper'

    @accepts(Dict(
        'webdav_update',
        Str('protocol', enum=['HTTP', 'HTTPS', "HTTPHTTPS"]),
        Int('tcpport'),
        Int('tcpportssl'),
        Str('password'),
        Str('htauth', enum=['NONE', 'BASIC', 'DIGEST']),
        Int('certssl', null=True),
        update=True
    ))
    async def do_update(self, data):
        old = await self.config()

        if old['certssl']:
            old['certssl'] = old['certssl']['id']

        new = old.copy()
        new.update(data)

        await self.lower(new)
        await self.validate(new, 'webdav_update')
        await self._update_service(old, new)

        if new['certssl'] and new['protocol'] != 'http':
            await self.middleware.call('service.start', 'ssl')

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
            data['certssl'] = await self.middleware.call(
                'certificate.query',
                [['id', '=', data['certssl']['id']]],
                {'get': True}
            )

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
        if data.get('protocol') != 'http' and not (
                await self.middleware.call('certificate.query', [['id', '=', cert_ssl]])
        ):
            verrors.add(
                f"{schema_name}.certssl",
                'WebDAV SSL protocol specified without choosing a certificate'
            )

        if verrors:
            raise verrors

        return data
