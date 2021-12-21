from middlewared.schema import Any, Str, Ref, Int, Dict, Bool, accepts
from middlewared.service import Service, private, job, filterable
from middlewared.utils import filter_list
from middlewared.service_exception import CallError, MatchNotFound

from collections import namedtuple
import os
import time
import pwd
import grp
import json


class ClusterCacheService(Service):
    tdb_options = {
        "cluster": True,
        "data_type": "STRING"
    }

    class Config:
        private = True

    @accepts(Str('key'))
    async def get(self, key):
        """
        Get `key` from cache.

        Raises:
            KeyError: not found in the cache
            CallError: issue with clustered key-value store

        CLOCK_REALTIME because clustered
        """
        payload = {
            "name": 'middlewared',
            "key": key,
            "tdb-options": self.tdb_options
        }
        try:
            tdb_value = await self.middleware.call('tdb.fetch', payload)
        except MatchNotFound:
            raise KeyError(key)

        expires = float(tdb_value[:12])
        now = time.clock_gettime(time.CLOCK_REALTIME)
        if expires and now > expires:
            await self.middleware.call('tdb.remove', payload)
            raise KeyError(f'{key} has expired')

        is_encrypted = bool(int(tdb_value[14]))
        if is_encrypted:
            raise NotImplementedError

        data = json.loads(tdb_value[18:])
        return data

    @accepts(Str('key'))
    async def pop(self, key):
        """
        Removes and returns `key` from cache.
        """
        payload = {
            "name": 'middlewared',
            "key": key,
            "tdb-options": self.tdb_options
        }
        try:
            tdb_value = await self.middleware.call('tdb.fetch', payload)
        except MatchNotFound:
            tdb_value = None

        if tdb_value:
            await self.middleware.call('tdb.remove', payload)
            # Will uncomment / add handling for private entries
            # once there's a cluster-wide method for encrypting data
            # is_encrypted = bool(int(tdb_value[14]))
            tdb_value = json.loads(tdb_value[18:])

        return tdb_value

    @accepts(Str('key'))
    async def has_key(self, key):
        try:
            await self.middleware.call('tdb.fetch', {
                "name": 'middlewared',
                "key": key,
                "tdb-options": self.tdb_options
            })
            return True
        except MatchNotFound:
            return False

    @accepts(
        Str('key'),
        Dict('value', additional_attrs=True),
        Int('timeout', default=0),
        Dict('options', Str('flag', enum=["CREATE", "REPLACE"], default=None, null=True), Bool('private', default=False),)
    )
    async def put(self, key, value, timeout, options):
        """
        Put `key` of `value` in the cache. `timeout` specifies time limit
        after which it will be removed.

        The following options are supported:
        `flag` optionally specifies insertion behavior.
        `CREATE` flag raises KeyError if entry exists. `UPDATE` flag
        raises KeyError if entry does not exist. When no flags are specified
        then entry is simply inserted.

        `private` determines whether data should be encrypted before being
        committed to underlying storage backend.
        """
        if options['private']:
            # will implement in later commit
            raise NotImplementedError

        if timeout != 0:
            ts = f'{time.clock_gettime(time.CLOCK_REALTIME) + timeout:.2f}'
        else:
            ts = '0000000000.00'

        tdb_key = key

        # This format must not be changed without careful consideration
        # Zeros are left as padding in middle to expand boolean options if needed
        tdb_val = f'{ts}{int(options["private"])}0000{json.dumps(value)}'

        if options['flag']:
            has_entry = False
            try:
                has_entry = bool(await self.get(tdb_key))
            except KeyError:
                pass

            if options['flag'] == "CREATE" and has_entry:
                raise KeyError(key)

            if options['flag'] == "UPDATE" and not has_entry:
                raise KeyError(key)

        await self.middleware.call('tdb.store', {
            'name': 'middlewared',
            'key': tdb_key,
            'value': {'payload': tdb_val},
            'tdb-options': self.tdb_options
        })
        return

    @filterable
    async def query(self, filters, options):
        def cache_convert_fn(tdb_key, tdb_val, entries):
            entries.append({
                "key": tdb_key,
                "timeout": float(tdb_val[:12]),
                "private": bool(int(tdb_val[14])),
                "value": json.loads(tdb_val[18:])
            })
            return True

        if not filters:
            filters = []
        if not options:
            options = {}

        parsed = []
        tdb_entries = await self.middleware.call('tdb.entries', {
            'name': 'middlewared',
            'tdb-options': self.tdb_options
        })
        for entry in tdb_entries:
            cache_convert_fn(entry['key'], entry['val'], parsed)

        return filter_list(parsed, filters, options)


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
        Dict('options', Bool('synthesize', default=False))
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
                                                        who_str, who_id)
                    entry = await self.middleware.call('idmap.synthetic_user',
                                                       ds.lower(), pwdobj)
                else:
                    grpobj = await self.middleware.call('dscache.get_uncached_group',
                                                        who_str, who_id)
                    entry = await self.middleware.call('idmap.synthetic_group',
                                                       ds.lower(), grpobj)
                await self.insert(ds, data['idtype'], entry)
            except KeyError:
                entry = None

        elif not entry:
            raise KeyError(who_str if who_str else who_id)

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

    def get_uncached_user(self, username=None, uid=None, getgroups=False):
        """
        Returns dictionary containing pwd_struct data for
        the specified user or uid. Will raise an exception
        if the user does not exist. This method is appropriate
        for user validation.
        """
        if username:
            u = pwd.getpwnam(username)
        elif uid is not None:
            u = pwd.getpwuid(uid)
        else:
            return {}

        user_obj = {
            'pw_name': u.pw_name,
            'pw_uid': u.pw_uid,
            'pw_gid': u.pw_gid,
            'pw_gecos': u.pw_gecos,
            'pw_dir': u.pw_dir,
            'pw_shell': u.pw_shell,
        }
        if getgroups:
            user_obj['grouplist'] = os.getgrouplist(u.pw_name, u.pw_gid)

        return user_obj

    def get_uncached_group(self, groupname=None, gid=None):
        """
        Returns dictionary containing grp_struct data for
        the specified group or gid. Will raise an exception
        if the group does not exist. This method is appropriate
        for group validation.
        """
        if groupname:
            g = grp.getgrnam(groupname)
        elif gid is not None:
            g = grp.getgrgid(gid)
        else:
            return {}
        return {
            'gr_name': g.gr_name,
            'gr_gid': g.gr_gid,
            'gr_mem': g.gr_mem
        }

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

        is_name_check = bool(filters and len(filters) == 1 and filters[0][0] in ['username', 'name'])
        is_id_check = bool(filters and len(filters) == 1 and filters[0][0] in ['uid', 'gid'])

        res.extend((await self.middleware.call(f'{objtype.lower()[:-1]}.query', filters, options)))

        for dstype, state in ds_state.items():
            if state != 'DISABLED':
                enabled_ds = dstype
                break

        if not enabled_ds:
            return res

        if is_name_check and filters[0][1] == '=':
            # exists in local sqlite database, return results
            if res:
                return res

            entry = await self.retrieve(enabled_ds.upper(), {
                'idtype': objtype[:-1],
                'who': filters[0][2],
            }, {'synthesize': True})
            return [entry] if entry else []

        if is_id_check and filters[0][1] == '=':
            # exists in local sqlite database, return results
            if res:
                return res

            entry = await self.retrieve(enabled_ds.upper(), {
                'idtype': objtype[:-1],
                'id': filters[0][2],
            }, {'synthesize': True})
            return [entry] if entry else []

        entries = await self.entries(enabled_ds.upper(), objtype[:-1])
        if 'SMB' in extra.get('additional_information', []):
            for entry in entries:
                sid = await self.middleware.call('idmap.unixid_to_sid', {
                    'id_type': objtype[:-1],
                    'id': entry[f'{objtype[0].lower()}id'],
                })
                name_key = "username" if objtype == 'USERS' else 'group'
                entry.update({
                    'nt_name': entry[name_key],
                    'sid': sid,
                })

        entries_by_id = sorted(entries, key=lambda i: i['id'])
        res.extend(filter_list(entries_by_id, filters, options))
        return res

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
