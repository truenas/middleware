from middlewared.schema import accepts, Bool, Dict, Int, List, Str
from middlewared.validators import Range
from middlewared.service import SystemServiceService, ValidationErrors, private

import ipaddress
import re

RE_IP_PORT = re.compile(r'^(.+?)(:[0-9]+)?$')


class ISCSIGlobalService(SystemServiceService):

    class Config:
        datastore_extend = 'iscsi.global.config_extend'
        datastore_prefix = 'iscsi_'
        service = 'iscsitarget'
        service_model = 'iscsitargetglobalconfiguration'
        namespace = 'iscsi.global'

    @private
    def config_extend(self, data):
        data['isns_servers'] = data['isns_servers'].split()
        return data

    @accepts(Dict(
        'iscsiglobal_update',
        Str('basename'),
        List('isns_servers', items=[Str('server')]),
        Int('pool_avail_threshold', validators=[Range(min=1, max=99)]),
        Bool('alua', default=False),
    ))
    async def do_update(self, data):
        """
        `alua` is a no-op for FreeNAS.
        """
        old = await self.config()

        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()

        servers = data.get('isns_servers') or []
        for server in servers:
            reg = RE_IP_PORT.search(server)
            if reg:
                ip = reg.group(1)
                if ip and ip[0] == '[' and ip[-1] == ']':
                    ip = ip[1:-1]
                try:
                    ipaddress.ip_address(ip)
                    continue
                except ValueError:
                    pass
            verrors.add('iscsiglobal_update.isns_servers', f'Server "{server}" is not a valid IP(:PORT)? tuple.')

        if verrors:
            raise verrors

        new['isns_servers'] = '\n'.join(servers)

        await self._update_service(old, new)

        if old['alua'] != new['alua']:
            await self.middleware.call('service.start', 'ix-loader')

        return await self.config()
