from middlewared.utils.itertools import batched
from middlewared.utils.directoryservices.constants import (
    DSType
)
from middlewared.utils.nss import pwd, grp
from middlewared.plugins.idmap_.idmap_constants import (
    IDType,
    MAX_REQUEST_LENGTH,
    SID_BUILTIN_PREFIX,
    SID_LOCAL_USER_PREFIX,
    SID_LOCAL_GROUP_PREFIX,
)
from middlewared.service_exception import CallError
from time import sleep


class CacheMixin:
    CACHE_DOMAIN_ONLINE_CHECK_TRIES = 60

    def _cache_online_check(self) -> bool:
        """
        This method provides way for individual services to wait until
        state is settled before filling cache.
        """
        return True

    def _cache_online_check_wait(self) -> None:
        tries = 0
        while tries <= self.CACHE_DOMAIN_ONLINE_CHECK_TRIES:
            if self._cache_online_check():
                return

            sleep(1)

        raise CallError('Timeout out waiting for domain to come online')

    def _cache_dom_sid_info(self) -> None:
        """
        Retrieve idmap ranges for trusted domains and return as dictionary
        keyed by sid

        Sample entry:
        'S-1-5-21-<domain subauths>': {'range_low': <int>, 'range_high': <int>}

        Currently this is only implemented for Active Directory, but in future
        we can expand to also include trust information for IPA domains.
        """
        pass

    def _add_sid_info_to_entries(self, nss_entries: list, dom_by_sid: dict) -> list:
        to_remove = []
        idmaps = self.call_sync('idmap.convert_unixids', nss_entries)

        for idx, entry in enumerate(nss_entries):
            unixkey = f'{IDType[entry["id_type"]].wbc_str()}:{entry["id"]}'
            if unixkey not in idmaps['mapped']:
                # not all users / groups in SSSD have SIDs
                # and so we'll leave them with a null SID and
                continue

            idmap_entry = idmaps['mapped'][unixkey]
            if idmap_entry['sid'].startswith((SID_LOCAL_GROUP_PREFIX, SID_LOCAL_USER_PREFIX)):
                self.logger.warning('%s [%d] collides with local user or group. '
                                    'Omitting from cache', entry['id_type'], entry['id'])
                to_remove.append(idx)
                continue

            if idmap_entry['sid'].startswith(SID_BUILTIN_PREFIX):
                # We don't want users to select auto-generated builtin groups
                to_remove.append(idx)
                continue

            entry['sid'] = idmap_entry['sid']
            entry['id_type'] = idmap_entry['id_type']
            if dom_by_sid:
                entry['domain_info'] = dom_by_sid[idmap_entry['sid'].rsplit('-', 1)[0]]

        to_remove.reverse()
        for idx in to_remove:
            nss_entries.pop(idx)

        return nss_entries

    def _get_entries_for_cache(self, entry_type: str, dom_by_sid: dict) -> list:
        """
        This generator yields batches of NSS entries as tuples containing
        100 entries. This avoids having to allocate huge amounts of memory
        to handle perhaps tens of thousands of individual users and groups
        """
        out = []
        match entry_type:
            case IDType.USER:
                nss_fn = pwd.iterpw
            case IDType.GROUP:
                nss_fn = grp.itergrp
            case _:
                raise ValueError(f'{entry_type}: unexpected `entry_type`')

        nss = nss_fn(module=self._nss_module)
        for entries in batched(nss, MAX_REQUEST_LENGTH):
            for entry in entries:
                out.append({
                    'id': entry.pw_uid if entry_type is IDType.USER else entry.gr_gid,
                    'sid': None,
                    'nss': entry,
                    'id_type': entry_type.name,
                    'domain_info': None
                })

            """
            Depending on the directory sevice we may need to add SID
            information to the NSS entries.
            """
            if not self._has_sids:
                yield out
            else:
                yield self._add_sid_info_to_entries(out, dom_by_sid)

    def fill_cache(self) -> None:
        """
        Populate our directory services cache based on NSS results from
        the domain controller / LDAP server.
        """
        if not self.config['enumerate']:
            return

        self._assert_is_active()

        # Give the service a chance to settle down
        self._cache_online_check_wait()

        dom_by_sid = self._cache_dom_sid_info()
        if self._ds_type == DSType.AD:
            domain_info = self.call_sync(
                'idmap.query',
                [["domain_info", "!=", None]],
                {'extra': {'additional_information': ['DOMAIN_INFO']}}
            )
            dom_by_sid = {dom['domain_info']['sid']: dom for dom in domain_info}
        else:
            dom_by_sid = None

        user_cnt = 0
        group_cnt = 0

        # wipe out any existing entries
        self.call_sync('tdb.wipe', {'name': f'{self.name}_user'})
        for users in self._get_entries_for_cache(IDType.USER, dom_by_sid):
            for u in users:
                user_data = u['nss']
                if u['domain_info']:
                    rid = int(u['sid'].rsplit('-', 1)[1])
                    _id = 100000 + u['domain_info']['range_low'] + rid
                else:
                    _id = 100000000 + user_cnt

                entry = {
                    'id': _id,
                    'uid': user_data.pw_uid,
                    'username': user_data.pw_name,
                    'unixhash': None,
                    'smbhash': None,
                    'group': {},
                    'home': user_data.pw_dir,
                    'shell': user_data.pw_shell,
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
                    'id_type_both': u['id_type'] == 'BOTH',
                    'nt_name': user_data.pw_name,
                    'smb': u['sid'] is not None,
                    'sid': u['sid'],
                }
                self.call_sync(
                    'directoryservices.cache.insert',
                    self._name.upper(), 'USER', entry
                )
                user_cnt += 1

        # wipe out any existing entries
        self.call_sync('tdb.wipe', {'name': f'{self.name}_group'})
        for groups in self._get_entries_for_cache(IDType.GROUP, dom_by_sid):
            for g in groups:
                group_data = g['nss']
                if g['domain_info']:
                    rid = int(g['sid'].rsplit('-', 1)[1])
                    _id = 100000 + g['domain_info']['range_low'] + rid
                else:
                    _id = 100000000 + group_cnt

                entry = {
                    'id': _id,
                    'gid': group_data.gr_gid,
                    'name': group_data.gr_name,
                    'group': group_data.gr_name,
                    'builtin': False,
                    'sudo_commands': [],
                    'sudo_commands_nopasswd': [],
                    'users': [],
                    'local': False,
                    'id_type_both': g['id_type'] == 'BOTH',
                    'nt_name': group_data.gr_name,
                    'smb': g['sid'] is not None,
                    'sid': g['sid'],
                }
                self.call_sync(
                    'directoryservices.cache.insert',
                    self._name.upper(), 'GROUP', entry
                )
                group_cnt += 1
