from middlewared.schema import Bool, Dict, IPAddr, List, Str
from middlewared.service import SystemServiceService, ValidationErrors, accepts, private

import re


LOGLEVEL_MAP = {
    '0': 'NONE',
    '1': 'MINIMUM',
    '2': 'NORMAL',
    '3': 'FULL',
    '10': 'DEBUG',
}
RE_NETBIOSNAME = re.compile(r"^[a-zA-Z0-9\.\-_!@#\$%^&\(\)'\{\}~]{1,15}$")


class SMBService(SystemServiceService):

    class Config:
        service = 'cifs'
        service_verb = 'restart'
        datastore = 'services.cifs'
        datastore_extend = 'smb.smb_extend'
        datastore_prefix = 'cifs_srv_'

    @private
    async def smb_extend(self, smb):
        """Extend smb for netbios."""
        if not await self.middleware.call('notifier.is_freenas') and await self.middleware.call('notifier.failover_node') == 'B':
            smb['netbiosname'] = smb['netbiosname_b']

        for i in ('aio_enable', 'aio_rs', 'aio_ws'):
            smb.pop(i, None)

        smb['loglevel'] = LOGLEVEL_MAP.get(smb['loglevel'])

        return smb

    async def __validate_netbios_name(self, name):
        return RE_NETBIOSNAME.match(name)

    @accepts(Dict(
        'smb_update',
        Str('netbiosname'),
        Str('netbiosname_b'),
        Str('netbiosalias'),
        Str('workgroup'),
        Str('description'),
        Str('doscharset', enum=[
            'CP437', 'CP850', 'CP852', 'CP866', 'CP932', 'CP949', 'CP950', 'CP1026', 'CP1251',
            'ASCII',
        ]),
        Str('unixcharset', enum=[
            'UTF-8', 'ISO-8859-1', 'ISO-8859-15', 'GB2312', 'EUC-JP', 'ASCII',
        ]),
        Str('loglevel', enum=['NONE', 'MINIMUM', 'NORMAL', 'FULL', 'DEBUG']),
        Bool('syslog'),
        Bool('localmaster'),
        Bool('domain_logons'),
        Bool('timeserver'),
        Str('guest'),
        Str('filemask'),
        Str('dirmask'),
        Bool('nullpw'),
        Bool('unixext'),
        Bool('zeroconf'),
        Bool('hostlookup'),
        Bool('allow_execute_always'),
        Bool('obey_pam_restrictions'),
        Bool('ntlmv1_auth'),
        List('bindip', items=[IPAddr('ip')]),
        Str('smb_options'),
        update=True,
    ))
    async def do_update(self, data):
        old = await self.config()

        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()

        for i in ('workgroup', 'netbiosname', 'netbiosname_b', 'netbiosalias'):
            if i not in data or not data[i]:
                continue
            if not await self.__validate_netbios_name(data[i]):
                verrors.add(f'smb_update.{i}', 'Invalid NetBIOS name')

        if new['netbiosname'] and new['netbiosname'].lower() == new['workgroup'].lower():
            verrors.add('smb_update.netbiosname', 'NetBIOS and Workgroup must be unique')

        for i in ('filemask', 'dirmask'):
            if i not in data or not data[i]:
                continue
            try:
                if int(data[i], 8) & ~0o11777:
                    raise ValueError('Not an octet')
            except (ValueError, TypeError):
                verrors.add(f'smb_update.{i}', 'Not a valid mask')

        if verrors:
            raise verrors

        # TODO: consider using bidict
        for k, v in LOGLEVEL_MAP.items():
            if new['loglevel'] == v:
                new['loglevel'] = k
                break

        await self._update_service(old, new)

        return await self.config()
