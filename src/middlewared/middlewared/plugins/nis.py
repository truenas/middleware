import asyncio
import enum
import errno
import subprocess

from middlewared.schema import accepts, Bool, Dict, List, Str
from middlewared.service import job, private, ConfigService
from middlewared.service_exception import CallError
from middlewared.utils import run


class DSStatus(enum.Enum):
    """
    Following items are used for cache entries indicating the status of the
    Directory Service.
    :FAULTED: Directory Service is enabled, but not HEALTHY.
    :LEAVING: Directory Service is in process of stopping.
    :JOINING: Directory Service is in process of starting.
    :HEALTHY: Directory Service is enabled, and last status check has passed.
    There is no "DISABLED" DSStatus because this is controlled by the "enable" checkbox.
    This is a design decision to avoid conflict between the checkbox and the cache entry.
    """
    FAULTED = 1
    LEAVING = 2
    JOINING = 3
    HEALTHY = 4


class NISService(ConfigService):
    class Config:
        service = "nis"
        datastore = 'directoryservice.nis'
        datastore_extend = "nis.nis_extend"
        datastore_prefix = "nis_"

    @private
    async def nis_extend(self, nis):
        nis['servers'] = nis['servers'].split(',') if nis['servers'] else []
        return nis

    @private
    async def nis_compress(self, nis):
        nis['servers'] = ','.join(nis['servers'])
        return nis

    @accepts(Dict(
        'nis_update',
        Str('domain'),
        List('servers'),
        Bool('secure_mode'),
        Bool('manycast'),
        Bool('enable'),
        update=True
    ))
    async def do_update(self, data):
        """
        Update NIS Service Configuration.

        `domain` is the name of NIS domain.

        `servers` is a list of hostnames/IP addresses.

        `secure_mode` when enabled sets ypbind(8) to refuse binding to any NIS server not running as root on a
        TCP port over 1024.

        `manycast` when enabled sets ypbind(8) to bind to the server that responds the fastest.

        `enable` when true disables the configuration of the NIS service.
        """
        must_reload = False
        old = await self.config()
        new = old.copy()
        new.update(data)
        if old != new:
            must_reload = True
        await self.nis_compress(new)
        await self.middleware.call(
            'datastore.update',
            'directoryservice.nis',
            old['id'],
            new,
            {'prefix': 'nis_'}
        )

        if must_reload:
            if new['enable']:
                await self.middleware.call('nis.start')
            else:
                await self.middleware.call('nis.stop')

        return await self.config()

    @private
    async def __set_state(self, state):
        await self.middleware.call('cache.put', 'NIS_State', state.name)

    @private
    async def get_state(self):
        """
        Check the state of the NIS Directory Service.
        See DSStatus for definitions of return values.
        :DISABLED: Service is not enabled.
        If for some reason, the cache entry indicating Directory Service state
        does not exist, re-run a status check to generate a key, then return it.
        """
        nis = await self.config()
        if not nis['enable']:
            return 'DISABLED'
        else:
            try:
                return (await self.middleware.call('cache.get', 'NIS_State'))
            except KeyError:
                await self.started()
                return (await self.middleware.call('cache.get', 'NIS_State'))

    @private
    async def start(self):
        """
        Refuse to start service if the service is alreading in process of starting or stopping.
        If state is 'HEALTHY' or 'FAULTED', then stop the service first before restarting it to ensure
        that the service begins in a clean state.
        """
        state = await self.get_state()
        nis = await self.config()
        if state in ['FAULTED', 'HEALTHY']:
            await self.stop()

        if state in ['EXITING', 'JOINING']:
            raise CallError(f'Current state of NIS service is: [{state}]. Wait until operation completes.', errno.EBUSY)

        await self.__set_state(DSStatus['JOINING'])
        await self.middleware.call('datastore.update', 'directoryservice.nis', nis['id'], {'nis_enable': True})
        await self.middleware.call('etc.generate', 'rc')
        await self.middleware.call('etc.generate', 'pam')
        await self.middleware.call('etc.generate', 'hostname')
        await self.middleware.call('etc.generate', 'nss')
        setnisdomain = await run(['/bin/domainname', nis['domain']], check=False)
        if setnisdomain.returncode != 0:
            await self.__set_state(DSStatus['FAULTED'])
            raise CallError(f'Failed to set NIS Domain to [{nis["domain"]}]: {setnisdomain.stderr.decode()}')

        ypbind = await run(['/usr/sbin/service', 'ypbind', 'onestart'], check=False)
        if ypbind.returncode != 0:
            await self.__set_state(DSStatus['FAULTED'])
            raise CallError(f'ypbind failed: {ypbind.stderr.decode()}')

        await self.__set_state(DSStatus['HEALTHY'])
        self.logger.debug(f'NIS service successfully started. Setting state to HEALTHY.')
        await self.middleware.call('nis.cache', 'fill')
        return True

    @private
    async def __ypwhich(self):
        """
        The return code from ypwhich is not a reliable health indicator. For example, RPC failure will return 0.
        There are edge cases where ypwhich can hang when NIS is misconfigured.
        """
        nis = await self.config()
        ypwhich = await run(['/usr/bin/ypwhich'], check=False)
        if ypwhich.returncode != 0:
            if nis['enable']:
                await self.__set_state(DSStatus['FAULTED'])
                self.logger.debug(f'NIS status check returned [{ypwhich.stderr.decode().strip()}]. Setting state to FAULTED.')
            return False
        if ypwhich.stderr:
            await self.__set_state(DSStatus['FAULTED'])
            raise CallError(f'NIS status check returned [{ypwhich.stderr.decode().strip()}]. Setting state to FAULTED.')
        return True

    @private
    async def started(self):
        ret = False
        try:
            ret = await asyncio.wait_for(self.__ypwhich(), timeout=5.0)
        except asyncio.TimeoutError:
            raise CallError('nis.started check timed out after 5 seconds.')

        if ret:
            await self.__set_state(DSStatus['HEALTHY'])
        return ret

    @private
    async def stop(self, force=False):
        """
        Remove NIS_state entry entirely after stopping ypbind. This is so that the 'enable' checkbox
        becomes the sole source of truth regarding a service's state when it is disabled.
        """
        state = await self.get_state()
        nis = await self.config()
        if not force:
            if state in ['LEAVING', 'JOINING']:
                raise CallError(f'Current state of NIS service is: [{state}]. Wait until operation completes.', errno.EBUSY)

        await self.__set_state(DSStatus['LEAVING'])
        await self.middleware.call('datastore.update', 'directoryservice.nis', nis['id'], {'nis_enable': False})

        ypbind = await run(['/usr/sbin/service', 'ypbind', 'onestop'], check=False)
        if ypbind.returncode != 0:
            await self.__set_state(DSStatus['FAULTED'])
            errmsg = ypbind.stderr.decode().strip()
            if 'ypbind not running' not in errmsg:
                raise CallError(f'ypbind failed to stop: [{ypbind.stderr.decode().strip()}]')

        await self.middleware.call('cache.pop', 'NIS_State')
        await self.middleware.call('etc.generate', 'rc')
        await self.middleware.call('etc.generate', 'pam')
        await self.middleware.call('etc.generate', 'hostname')
        await self.middleware.call('etc.generate', 'nss')
        await self.middleware.call('nis.cache', 'expire')
        self.logger.debug(f'NIS service successfully stopped. Setting state to DISABLED.')
        return True

    @private
    @job(lock=lambda args: 'fill_nis_cache')
    def fill_nis_cache(self, job, force=False):
        if self.middleware.call_sync('cache.has_key', 'NIS_cache') and not force:
            raise CallError('LDAP cache already exists. Refusing to generate cache.')

        self.middleware.call_sync('cache.pop', 'NIS_cache')
        pwd_list = pwd.getpwall()
        grp_list = grp.getgrall()

        local_uid_list = list(u['uid'] for u in self.middleware.call_sync('user.query'))
        local_gid_list = list(g['gid'] for g in self.middleware.call_sync('group.query'))
        cache_data = {'users': [], 'groups': []}

        for u in pwd_list:
            is_local_user = True if u.pw_uid in local_uid_list else False
            if is_local_user:
                continue

            cache_data['users'].append({
                'pw_name': u.pw_name,
                'pw_uid': u.pw_uid,
                'local': False
            })

        for g in grp_list:
            is_local_user = True if g.gr_gid in local_gid_list else False
            if is_local_user:
                continue

            cache_data['groups'].append({
                'gr_name': g.gr_name,
                'gr_gid': g.gr_gid,
                'local': False
            })

        self.middleware.call_sync('cache.put', 'NIS_cache', cache_data, 86400)

    @private
    async def get_cache(self):
        if not await self.middleware.call('cache.has_key', 'NIS_cache'):
            cache_job = await self.middleware.call('nis.fill_nis_cache')
            await cache_job.wait()
            self.logger.debug('cache fill is in progress.')
            return {}
        return await self.middleware.call('cache.get', 'nis_cache')

    @private
    async def get_userorgroup_legacy(self, entry_type='users', obj=None):
        if entry_type == 'users':
            if await self.middleware.call('user.query', [('username', '=', obj)]):
                return None
        else:
            if await self.middleware.call('group.query', [('group', '=', obj)]):
                return None

        nis_cache = await self.get_cache()
        if not nis_cache:
            return await self.middleware.call('dscache.get_uncached_userorgroup_legacy', entry_type, obj)

        if entry_type == 'users':
            ret = list(filter(lambda x: x['pw_name'] == obj, nis_cache[entry_type]))
        else:
            ret = list(filter(lambda x: x['gr_name'] == obj, nis_cache[entry_type]))
        if not ret:
            return await self.middleware.call('dscache.get_uncached_userorgroup_legacy', entry_type, obj)

        return ret[0]
