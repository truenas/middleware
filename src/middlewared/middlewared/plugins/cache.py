from middlewared.schema import Any, Str, accepts, Int, Dict
from middlewared.service import Service, private, filterable
from middlewared.utils import filter_list

from collections import namedtuple
import time
import pwd
import grp


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

    @private
    def get_uncached_user(self, username=None, uid=None):
        if username:
            u = pwd.getpwnam(username)
        elif uid is not None:
            u = pwd.getpwuid(uid)
        else:
            return {}
        return {
            'pw_name': u.pw_name,
            'pw_uid': u.pw_uid,
            'pw_gid': u.pw_gid,
            'pw_gecos': u.pw_gecos,
            'pw_dir': u.pw_dir,
            'pw_shell': u.pw_shell
        }

    @private
    def get_uncached_group(self, groupname=None, gid=None):
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

    @private
    async def query(self, objtype='USERS', filters=None, options=None):
        """
        Query User / Group cache with `query-filters` and `query-options`.

        `objtype`: 'USERS' or 'GROUPS'

        """
        ds_enabled = {}
        res = []
        for ds in ['activedirectory', 'ldap', 'nis']:
            ds_enabled.update({
                str(ds): True if await self.middleware.call(f'{ds}.get_state') != 'DISABLED' else False
            })

        if objtype == 'USERS':
            local_users = []
            for u in await self.middleware.call('user.query'):
                local_users.append({
                    'pw_name': u['username'],
                    'pw_uid': u['uid'],
                    'local': True,
                })
            res.extend(filter_list(local_users, filters, options))

        elif objtype == 'GROUPS':
            local_groups = []
            for g in await self.middleware.call('group.query'):
                local_groups.append({
                    'gr_name': g['group'],
                    'gr_gid': g['gid'],
                    'local': True,
                })
            res.extend(filter_list(local_groups, filters, options))

        for dstype, enabled in ds_enabled.items():
            if enabled:
                res.extend(filter_list(
                    (await self.middleware.call(f'{dstype}.get_cache'))[objtype.lower()],
                    filters,
                    options
                ))

        return res

    @private
    async def refresh(self):
        """
        Force update of Directory Service Caches
        """
        for ds in ['activedirectory', 'ldap', 'nis']:
            ds_state = await self.middleware.call(f'{ds}.get_state')
            if ds_state == 'HEALTHY':
                await self.middleware.call(f'{ds}.fill_cache', True)
            elif ds_state != 'DISABLED':
                self.logger.debug('Unable to refresh [%s] cache, state is: %s' % (ds, ds_state))
