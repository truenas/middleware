from middlewared.plugins.idmap_.utils import (
    IDType,
    SID_LOCAL_USER_PREFIX,
    SID_LOCAL_GROUP_PREFIX,
)
from middlewared.service import Service, private, job
from middlewared.service_exception import CallError
from middlewared.utils.nss import pwd, grp
from middlewared.utils.nss.nss_common import NssModule
from time import sleep


class ActiveDirectoryService(Service):
    class Config:
        service = "activedirectory"

    @private
    def get_entries(self, data):
        ret = []
        entry_type = data.get('entry_type')

        domain_info = self.middleware.call_sync(
            'idmap.query', [], {'extra': {'additional_information': ['DOMAIN_INFO']}}
        )
        for dom in domain_info.copy():
            if not dom['domain_info']:
                domain_info.remove(dom)

        dom_by_sid = {x['domain_info']['sid']: x for x in domain_info}

        if entry_type == 'USER':
            entries = pwd.getpwall(module=NssModule.WINBIND.name)[NssModule.WINBIND.name]
            for i in entries:
                ret.append({"id": i.pw_uid, "sid": None, "nss": i, "id_type": entry_type})
        else:
            entries = grp.getgrall(module=NssModule.WINBIND.name)[NssModule.WINBIND.name]
            for i in entries:
                ret.append({"id": i.gr_gid, "sid": None, "nss": i, "id_type": entry_type})

        idmaps = self.middleware.call_sync('idmap.convert_unixids', ret)
        to_remove = []

        for idx, entry in enumerate(ret):
            unixkey = f'{IDType[entry["id_type"]].wbc_str()}:{entry["id"]}'
            if unixkey not in idmaps['mapped']:
                self.logger.warning('%s: failed to lookup SID', unixkey)
                to_remove.append(idx)
                continue

            sid = idmaps['mapped'][unixkey]['sid']
            if sid.startswith((SID_LOCAL_GROUP_PREFIX, SID_LOCAL_USER_PREFIX)):
                self.logger.warning('%s [%d] collides with local user or group. '
                                    'Omitting from cache', entry['id_type'], entry['id'])
                to_remove.append(idx)
                continue

            entry['sid'] = sid
            entry['domain_info'] = dom_by_sid[entry['sid'].rsplit('-', 1)[0]]

        to_remove.reverse()
        for idx in to_remove:
            ret.pop(idx)

        return ret

    @private
    @job(lock='fill_ad_cache')
    def fill_cache(self, job, force=False):
        def online_check_wait():
            waited = 0
            while waited <= 60:
                offline_domains = self.middleware.call_sync(
                    'idmap.online_status',
                    [['online', '=', False]]
                )
                if not offline_domains:
                    return

                self.logger.debug('Waiting for the following domains to come online: %s',
                                  ', '.join([x['domain'] for x in offline_domains]))
                sleep(1)
                waited += 1

            raise CallError('Timed out while waiting for domain to come online')

        ad = self.middleware.call_sync('activedirectory.config')
        id_type_both_backends = [
            'RID',
            'AUTORID'
        ]
        online_check_wait()

        if ad['disable_freenas_cache']:
            return

        users = self.get_entries({'entry_type': 'USER', 'cache_enabled': not ad['disable_freenas_cache']})
        for u in users:
            user_data = u['nss']
            rid = int(u['sid'].rsplit('-', 1)[1])

            entry = {
                'id': 100000 + u['domain_info']['range_low'] + rid,
                'uid': user_data.pw_uid,
                'username': user_data.pw_name,
                'unixhash': None,
                'smbhash': None,
                'group': {},
                'home': '',
                'shell': '',
                'full_name': user_data.pw_gecos,
                'builtin': False,
                'email': '',
                'password_disabled': False,
                'locked': False,
                'sudo_commands': [],
                'sudo_commands_nopasswd': False,
                'attributes': {},
                'groups': [],
                'sshpubkey': None,
                'local': False,
                'id_type_both': u['domain_info']['idmap_backend'] in id_type_both_backends,
                'nt_name': user_data.pw_name,
                'smb': True,
                'sid': u['sid'],
            }
            self.middleware.call_sync('directoryservices.cache.insert', self._config.namespace.upper(), 'USER', entry)

        groups = self.get_entries({'entry_type': 'GROUP', 'cache_enabled': not ad['disable_freenas_cache']})
        for g in groups:
            group_data = g['nss']
            rid = int(g['sid'].rsplit('-', 1)[1])

            entry = {
                'id': 100000 + g['domain_info']['range_low'] + rid,
                'gid': group_data.gr_gid,
                'name': group_data.gr_name,
                'group': group_data.gr_name,
                'builtin': False,
                'sudo_commands': [],
                'sudo_commands_nopasswd': [],
                'users': [],
                'local': False,
                'id_type_both': g['domain_info']['idmap_backend'] in id_type_both_backends,
                'nt_name': group_data.gr_name,
                'smb': True,
                'sid': g['sid'],
            }
            self.middleware.call_sync('directoryservices.cache.insert', self._config.namespace.upper(), 'GROUP', entry)

    @private
    async def get_cache(self):
        users = await self.middleware.call('directoryservices.cache.entries', self._config.namespace.upper(), 'USER')
        groups = await self.middleware.call('directoryservices.cache.entries', self._config.namespace.upper(), 'GROUP')
        return {"USERS": users, "GROUPS": groups}
