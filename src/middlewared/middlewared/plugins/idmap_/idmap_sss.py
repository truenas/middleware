import pysss_nss_idmap as sssclient

from .idmap_constants import IDType
from middlewared.utils.itertools import batched
from middlewared.service_exception import MatchNotFound


class SSSClient:

    def _username_to_entry(self, username):
        """
        Sample entry returned by pysss_nss_idmap

        `getsidbyusername`
        {'smbuser': {'sid': 'S-1-5-21-3696504179-2855309571-923743039-1020', 'type': 1}}

        `getidbysid`
        {'S-1-5-21-3696504179-2855309571-923743039-1020': {'id': 565200020, 'type': 1}}

        Sample of what we return:
        {'id_type': 'USER', 'id': 565200020, 'name': 'smbuser'}
        """
        if not (sid_entry := sssclient.getsidbyusername(username)):
            return None

        sid = sid_entry[username]['sid']
        id_type = sid_entry[username]['type']

        if not (id_entry := sssclient.getidbysid(sid)):
            return None

        return {
            'id_type': IDType(id_type).name,
            'id': id_entry[sid]['id'],
            'name': username,
            'sid': sid
        }

    def _groupname_to_sid(self, groupname):
        if not (sid_entry := sssclient.getsidbygroupname(groupname)):
            return None

        sid = sid_entry[groupname]['sid']
        id_type = sid_entry[groupname]['type']

        if not (id_entry := sssclient.getidbysid(sid)):
            return None

        return {
            'id_type': IDType(id_type).name,
            'id': id_entry[sid]['id'],
            'name': groupname,
            'sid': sid
        }

    def _gid_to_entry(self, gid):
        if not (sid_entry := sssclient.getsidbygid(gid)):
            return None

        sid = sid_entry[gid]['sid']
        id_type = sid_entry[gid]['type']

        if not (name_entry := sssclient.getnamebysid(sid)):
            return None

        return {
            'id_type': IDType(id_type).name,
            'id': gid,
            'name': name_entry[sid]['name'],
            'sid': sid
        }

    def _uid_to_entry(self, uid):
        if not (sid_entry := sssclient.getsidbyuid(uid)):
            return None

        sid = sid_entry[uid]['sid']
        id_type = sid_entry[uid]['type']

        if not (name_entry := sssclient.getnamebysid(sid)):
            return None

        return {
            'id_type': IDType(id_type).name,
            'id': uid,
            'name': name_entry[sid]['name'],
            'sid': sid
        }

    def _sid_to_entry(self, sid):
        if not (id_entry := sssclient.getidbysid(sid)):
            return None

        if not (name_entry := sssclient.getnamebysid(sid)):
            return None

        return {
            'id_type': IDType(id_entry[sid]['type']).name,
            'id': id_entry[id_entry[sid]]['id'],
            'name': name_entry[sid]['name'],
            'sid': sid
        }

    def sids_to_idmap_entries(self, sidlist):
        out = {'mapped': {}, 'unmapped': {}}
        for sid in sidlist:
            if not (entry := self._sid_to_entry(sid)):
                out['unmapped'][sid] = sid
                continue

            out['mapped'][sid] = entry

        return out

    def users_and_groups_to_idmap_entries(self, uidgids):
        out = {'mapped': {}, 'unmapped': {}}

        for uidgid in uidgids:
            match uidgid['id_type']:
                case 'GROUP':
                    entry = self._gid_to_entry(uidgid['id'])
                case 'USER':
                    entry = self._uid_to_entry(uidgid['id'])
                case 'BOTH':
                    if not (entry := self._gid_to_entry(uidgid['id'])):
                        entry = self._uid_to_entry(uidgid['id'])
                case _:
                    raise ValueError(f'{uidgid["id_type"]}: Unknown id_type')

            key = f'{IDType[uidgid["id_type"]].wbc_str()}:{uidgid["id"]}'
            if not entry:
                out['unmapped'][key] = entry
                continue

            out['mapped'][key] = entry

        return out

    def sid_to_idmap_entry(self, sid):
        if not (entry := self._sid_to_entry(sid)):
            raise MatchNotFound(sid)

        return entry

    def name_to_idmap_entry(self, name):
        if entry := self._groupname_to_sid(name):
            return entry

        if entry := self._username_to_sid(name):
            return entry

        raise MatchNotFound(name)

    def uidgid_to_idmap_entry(self, data):
        mapped = self.users_and_groups_to_idmap_entries([data])['mapped']
        if not mapped:
            raise MatchNotFound(str(data))

        key = f'{IDType[data["id_type"]].wbc_str()}:{data["id"]}'
        return mapped[key]
