from middlewared.schema import Dict, Int, Str, ValidationErrors, accepts
from middlewared.service import SystemServiceService, private


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
        Int('certssl')
    ))
    async def do_update(self, data):
        old = await self.config()

        new = old.copy()
        new.update(data)

        await self.lower(new)
        await self.validate(new, 'webdav_update')
        await self._update_service(old, new)
        await self.upper(new)

        secure_protocol = False if new['protocol'] == 'HTTP' else True

        if new['certssl'] != 'NONE' and secure_protocol:
            await self.middleware.call('notifier.start_ssl', 'webdav')

        return new

    @private
    async def lower(self, data):
        data['protocol'] = data['protocol'].lower()
        data['htauth'] = data['htauth'].lower()

        return data

    @private
    async def upper(self, data):
        data['protocol'] = data['protocol'].upper()
        data['htauth'] = data['htauth'].upper()

        return data

    @private
    async def validate(self, data, schema_name):
        verrors = ValidationErrors()

        if (data.get('protocol') == 'HTTPHTTPS' and
                data.get('tcpport') == data.get('tcpportssl')):
            verrors.add(f"{schema_name}.tcpportssl",
                        'The HTTP and HTTPS ports cannot be the same!')

        if (data.get('protocol') != 'HTTP' and data.get('certssl') is None):
            verrors.add(
                f"{schema_name}.certssl",
                'Webdav SSL protocol specified without choosing a certificate'
            )

        if verrors:
            raise verrors

        return data
