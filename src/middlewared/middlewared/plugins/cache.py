from middlewared.schema import Any, Str, Ref, Int, Dict, Bool, accepts
from middlewared.service import Service, private, job, filterable
from middlewared.utils import filter_list
from middlewared.utils.nss import pwd, grp
from middlewared.service_exception import CallError, MatchNotFound
from middlewared.plugins.idmap_.utils import SID_LOCAL_USER_PREFIX, SID_LOCAL_GROUP_PREFIX

from collections import namedtuple
import errno
import os
import time


class CacheService(Service):

    class Config:
        private = True

    def __init__(self, *args, **kwargs):
        super(CacheService, self).__init__(*args, **kwargs)
        self.__cache = {}
        self.kv_tuple = namedtuple('Cache', ['value', 'timeout'])

    @accepts(Str('key'))
    def has_key(self, key):
        """
        Check if given `key` is in cache.
        """
        return key in self.__cache

    @accepts(Str('key'))
    def get(self, key):
        """
        Get `key` from cache.

        Raises:
            KeyError: not found in the cache
        """

        if self.__cache[key].timeout > 0:
            self.get_timeout(key)

        return self.__cache[key].value

    @accepts(Str('key'), Any('value'), Int('timeout', default=0))
    def put(self, key, value, timeout):
        """
        Put `key` of `value` in the cache.
        """

        if timeout != 0:
            timeout = time.monotonic() + timeout

        v = self.kv_tuple(value=value, timeout=timeout)
        self.__cache[key] = v

    @accepts(Str('key'))
    def pop(self, key):
        """
        Removes and returns `key` from cache.
        """
        cache = self.__cache.pop(key, None)

        if cache is not None:
            cache = cache.value

        return cache

    @private
    def get_timeout(self, key):
        """
        Check if 'key' has expired
        """
        now = time.monotonic()
        value, timeout = self.__cache[key]

        if now >= timeout:
            # Bust the cache
            del self.__cache[key]

            raise KeyError(f'{key} has expired')

    @private
    def get_or_put(self, key, timeout, method):
        try:
            return self.get(key)
        except KeyError:
            value = method()
            self.put(key, value, timeout)
            return value


class DSCache(Service):

    class Config:
        private = True

    @accepts(
        Str('directory_service', required=True, enum=["ACTIVEDIRECTORY", "LDAP"]),
        Str('idtype', enum=['USER', 'GROUP'], required=True),
        Dict('cache_entry', additional_attrs=True),
    )
    async def insert(self, ds, idtype, entry):
        if idtype == "GROUP":
            id_key = "gid"
            name_key = "name"
        else:
            id_key = "uid"
            name_key = "username"

        ops = [
            {"action": "SET", "key": f'ID_{entry[id_key]}', "val": entry},
            {"action": "SET", "key": f'NAME_{entry[name_key]}', "val": entry}
        ]
        await self.middleware.call('tdb.batch_ops', {
            "name": f'{ds.lower()}_{idtype.lower()}',
            "ops": ops
        })
        return True

    @accepts(
        Str('directory_service', required=True, enum=["ACTIVEDIRECTORY", "LDAP"]),
        Dict(
            'principal_info',
            Str('idtype', enum=['USER', 'GROUP']),
            Str('who'),
            Int('id'),
        ),
        Dict(
            'options',
            Bool('synthesize', default=False),
            Bool('smb', default=False)
        )
    )
    async def retrieve(self, ds, data, options):
        who_str = data.get('who')
        who_id = data.get('id')
        if who_str is None and who_id is None:
            raise CallError("`who` or `id` entry is required to uniquely "
                            "identify the entry to be retrieved.")

        tdb_name = f'{ds.lower()}_{data["idtype"].lower()}'
        prefix = "NAME" if who_str else "ID"
        tdb_key = f'{prefix}_{who_str if who_str else who_id}'
        name_key = "username" if data['idtype'] == 'USER' else 'group'

        try:
            entry = await self.middleware.call("tdb.fetch", {"name": tdb_name, "key": tdb_key})
        except MatchNotFound:
            entry = None

        if not entry and options['synthesize']:
            """
            if cache lacks entry, create one from passwd / grp info,
            insert into cache and return synthesized value.
            get_uncached_* will raise KeyError if NSS lookup fails.
            """
            try:
                if data['idtype'] == 'USER':
                    pwdobj = await self.middleware.call('dscache.get_uncached_user',
                                                        who_str, who_id, False, True)
                    if pwdobj['sid_info'] is None:
                        # This indicates that idmapping is significantly broken
                        return None

                    entry = await self.middleware.call('idmap.synthetic_user',
                                                       ds.lower(), pwdobj, pwdobj['sid_info']['sid'])
                    if entry is None:
                        return None
                else:
                    grpobj = await self.middleware.call('dscache.get_uncached_group',
                                                        who_str, who_id, True)

                    if grpobj['sid_info'] is None:
                        # This indicates that idmapping is significantly broken
                        return None

                    entry = await self.middleware.call('idmap.synthetic_group',
                                                       ds.lower(), grpobj, grpobj['sid_info']['sid'])
                    if entry is None:
                        return None

                await self.insert(ds, data['idtype'], entry)
                entry['nt_name'] = entry[name_key]
            except KeyError:
                entry = None

        elif not entry:
            raise KeyError(who_str if who_str else who_id)

        if entry and not options['smb']:
            entry['sid'] = None
            entry['nt_name'] = None

        if entry is not None:
            entry['roles'] = []

        return entry

    @accepts(
        Str('ds', required=True, enum=["ACTIVEDIRECTORY", "LDAP"]),
        Str('idtype', required=True, enum=["USER", "GROUP"]),
    )
    async def entries(self, ds, idtype):
        entries = await self.middleware.call('tdb.entries', {
            'name': f'{ds.lower()}_{idtype.lower()}',
            'query-filters': [('key', '^', 'ID')]
        })
        return [x['val'] for x in entries]

    def parse_domain_info(self, sid):
        if sid.startswith(SID_LOCAL_USER_PREFIX):
            return {'domain': 'LOCAL', 'domain_sid': None, 'online': True, 'activedirectory': False}

        domain_info = self.middleware.call_sync(
            'idmap.known_domains', [['sid', '=', sid.rsplit('-', 1)[0]]]
        )
        if not domain_info:
            return {'domain': 'UNKNOWN', 'domain_sid': None, 'online': False, 'activedirectory': False}

        return {
            'domain': domain_info[0]['netbios_domain'],
            'domain_sid': domain_info[0]['sid'],
            'online': domain_info[0]['online'],
            'activedirectory': 'ACTIVE_DIRECTORY' in domain_info[0]['domain_flags']['parsed']
        }

    def get_uncached_user(self, username=None, uid=None, getgroups=False, sid_info=False):
        """
        Returns dictionary containing pwd_struct data for
        the specified user or uid. Will raise an exception
        if the user does not exist. This method is appropriate
        for user validation.
        """
        if username:
            user_obj = pwd.getpwnam(username, module='ALL', as_dict=True)
        elif uid is not None:
            user_obj = pwd.getpwuid(uid, module='ALL', as_dict=True)
        else:
            return {}

        source = user_obj.pop('source')
        user_obj['local'] = source == 'FILES'

        if getgroups:
            user_obj['grouplist'] = os.getgrouplist(user_obj['pw_name'], user_obj['pw_gid'])

        if sid_info:
            try:
                if (idmap := self.middleware.call_sync('idmap.convert_unixids', [{
                    'id_type': 'USER',
                    'id': user_obj['pw_uid'],
                }])['mapped']):
                    sid = idmap[f'UID:{user_obj["pw_uid"]}']['sid']
                else:
                    sid = SID_LOCAL_USER_PREFIX + str(user_obj['pw_uid'])
            except CallError as e:
                # ENOENT means no winbindd entry for user
                # ENOTCONN means winbindd is stopped / can't be started
                # EAGAIN means the system dataset is hosed and needs to be fixed,
                # but we need to let it through so that it's very clear in logs
                if e.errno not in (errno.ENOENT, errno.ENOTCONN):
                    self.logger.error('Failed to retrieve SID for uid: %d', user_obj['pw_uid'], exc_info=True)
                sid = None
            except Exception:
                self.logger.error('Failed to retrieve SID for uid: %d', user_obj['pw_uid'], exc_info=True)
                sid = None

            if sid:
                user_obj['sid_info'] = {
                    'sid': sid,
                    'domain_information': self.parse_domain_info(sid)
                }
            else:
                user_obj['sid_info'] = None

        return user_obj

    def get_uncached_group(self, groupname=None, gid=None, sid_info=False):
        """
        Returns dictionary containing grp_struct data for
        the specified group or gid. Will raise an exception
        if the group does not exist. This method is appropriate
        for group validation.
        """
        if groupname:
            grp_obj = grp.getgrnam(groupname, module='ALL', as_dict=True)
        elif gid is not None:
            grp_obj = grp.getgrgid(gid, module='ALL', as_dict=True)
        else:
            return {}

        source = grp_obj.pop('source')
        grp_obj['local'] = source == 'FILES'

        if sid_info:
            try:
                if (idmap := self.middleware.call_sync('idmap.convert_unixids', [{
                    'id_type': 'GROUP',
                    'id': grp_obj['gr_gid'],
                }])['mapped']):
                    sid = idmap[f'GID:{grp_obj["gr_gid"]}']['sid']
                else:
                    sid = SID_LOCAL_GROUP_PREFIX + str(grp_obj['gr_gid'])
            except CallError as e:
                if e.errno not in (errno.ENOENT, errno.ENOTCONN):
                    self.logger.error('Failed to retrieve SID for gid: %d', grp_obj['gr_gid'], exc_info=True)
                sid = None
            except Exception:
                self.logger.error('Failed to retrieve SID for gid: %d', grp['gr_gid'], exc_info=True)
                sid = None

            if sid:
                grp_obj['sid_info'] = {
                    'sid': sid,
                    'domain_information': self.parse_domain_info(sid)
                }
            else:
                grp_obj['sid_info'] = None

        return grp_obj

    @accepts(
        Str('objtype', enum=['USERS', 'GROUPS'], default='USERS'),
        Ref('query-filters'),
        Ref('query-options'),
    )
    async def query(self, objtype, filters, options):
        """
        Query User / Group cache with `query-filters` and `query-options`.

        `objtype`: 'USERS' or 'GROUPS'
        """
        res = []
        ds_state = await self.middleware.call('directoryservices.get_state')
        enabled_ds = None
        extra = options.get("extra", {})
        get_smb = 'SMB' in extra.get('additional_information', [])
        options.pop('get', None)  # This needs to happen as otherwise `res` will become a list of keys of user attrs

        is_name_check = bool(filters and len(filters) == 1 and filters[0][0] in ['username', 'name'])
        is_id_check = bool(filters and len(filters) == 1 and filters[0][0] in ['uid', 'gid'])

        for dstype, state in ds_state.items():
            if state != 'DISABLED':
                enabled_ds = dstype
                break

        if not enabled_ds:
            return []

        if (is_name_check or is_id_check) and filters[0][1] == '=':
            key = 'who' if is_name_check else 'id'
            entry = await self.retrieve(enabled_ds.upper(), {
                'idtype': objtype[:-1],
                key: filters[0][2],
            }, {'synthesize': True, 'smb': get_smb})

            return [entry] if entry else []

        entries = await self.entries(enabled_ds.upper(), objtype[:-1])
        if not get_smb:
            for entry in entries:
                entry['sid'] = None
                entry['nt_name'] = None

        return sorted(entries, key=lambda i: i['id'])

    @job(lock="dscache_refresh")
    async def refresh(self, job):
        """
        This is called from a cronjob every 24 hours and when a user clicks on the
        UI button to 'rebuild directory service cache'.
        """
        for ds in ['activedirectory', 'ldap']:
            await self.middleware.call('tdb.wipe', {'name': f'{ds}_user'})
            await self.middleware.call('tdb.wipe', {'name': f'{ds}_group'})

            ds_state = await self.middleware.call(f'{ds}.get_state')

            if ds_state == 'HEALTHY':
                await job.wrap(await self.middleware.call(f'{ds}.fill_cache', True))
            elif ds_state != 'DISABLED':
                self.logger.debug('Unable to refresh [%s] cache, state is: %s' % (ds, ds_state))
