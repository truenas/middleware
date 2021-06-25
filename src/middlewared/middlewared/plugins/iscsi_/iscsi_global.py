import re

import middlewared.sqlalchemy as sa

from middlewared.schema import accepts, Bool, Dict, Int, List, Str
from middlewared.service import private, SystemServiceService, ValidationErrors
from middlewared.validators import IpAddress, Range

RE_IP_PORT = re.compile(r'^(.+?)(:[0-9]+)?$')


class ISCSIGlobalModel(sa.Model):
    __tablename__ = 'services_iscsitargetglobalconfiguration'

    id = sa.Column(sa.Integer(), primary_key=True)
    iscsi_basename = sa.Column(sa.String(120))
    iscsi_isns_servers = sa.Column(sa.Text())
    iscsi_pool_avail_threshold = sa.Column(sa.Integer(), nullable=True)
    iscsi_alua = sa.Column(sa.Boolean(), default=False)


class ISCSIGlobalService(SystemServiceService):

    class Config:
        datastore_extend = 'iscsi.global.config_extend'
        datastore_prefix = 'iscsi_'
        service = 'iscsitarget'
        service_model = 'iscsitargetglobalconfiguration'
        namespace = 'iscsi.global'
        cli_namespace = 'sharing.iscsi.global'

    @private
    def config_extend(self, data):
        data['isns_servers'] = data['isns_servers'].split()
        return data

    @accepts(Dict(
        'iscsiglobal_update',
        Str('basename'),
        List('isns_servers', items=[Str('server')]),
        Int('pool_avail_threshold', validators=[Range(min=1, max=99)], null=True),
        Bool('alua'),
        update=True
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
                    ip_validator = IpAddress()
                    ip_validator(ip)
                    continue
                except ValueError:
                    pass
            verrors.add('iscsiglobal_update.isns_servers', f'Server "{server}" is not a valid IP(:PORT)? tuple.')

        if verrors:
            raise verrors

        new['isns_servers'] = '\n'.join(servers)

        await self._update_service(old, new)

        if old['alua'] != new['alua']:
            await self.middleware.call('etc.generate', 'loader')

        return await self.config()

    async def alua_enabled(self):
        """
        Returns whether iSCSI ALUA is enabled or not.
        """
        if not await self.middleware.call('system.is_enterprise'):
            return False
        if not await self.middleware.call('failover.licensed'):
            return False

        license = await self.middleware.call('system.license')
        if license is not None and 'FIBRECHANNEL' in license['features']:
            return True

        return (await self.middleware.call('iscsi.global.config'))['alua']
