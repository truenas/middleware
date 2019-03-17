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
        nis.pop('id')
        return nis

    @private
    async def nis_compress(self, nis):
        nis['servers'] = ','.join(nis['servers'])
        nis.update({'id': 1})
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
        old = await self.config()
        new = old.copy()
        new.update(data)
        await self.nis_compress(new)
        await self.middleware.call(
            'datastore.update',
            'directoryservice.nis',
            '1',
            new,
            {'prefix': 'nis_'}
        )
        await self.nis_extend(new)

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
        nis = await self.middleware.call('nis.config')
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
        Refuse to start the service if a state has already been set in the cache. This is to prevent multiple
        simultaneous service starts. Even in faulted state, it is safer to cleanly stop the service before starting.
        Even in a faulted state, it is safer to cleanly stop the service before restarting.
        """
        state = await self.get_state()
        if state == 'FAULTED':
            raise CallError(f'NIS service is currently in faulted state. Review logs for error message or try clean restart of NIS service.', errno.EBUSY)

        if state == 'HEALTHY':
            raise CallError(f'NIS service is currently in healthy state. Valid command options are "restart" or "reload"', errno.EBUSY)

        if state != 'DISABLED':
            raise CallError(f'Current state of NIS service is: [{state}]. Wait until operation completes.', errno.EBUSY)

        await self.middleware.call('nis.update', {'enable': True})
        await self.__set_state(DSStatus['JOINING'])
        await self.middleware.call('etc.generate', 'rc')
        await self.middleware.call('etc.generate', 'pam')
        await self.middleware.call('etc.generate', 'hostname')
        await self.middleware.call('etc.generate', 'nss')
        nis = await self.middleware.call('nis.config')
        setnisdomain = await run(['/bin/domainname', nis['domain']], check=False)
        if setnisdomain.returncode != 0:
            await self.__set_state(DSStatus['FAULTED'])
            raise CallError(f'Failed to set NIS Domain to [{nis["domain"]}]: {setnisdomain.stderr.decode()}')

        ypbind = await run(['/usr/sbin/service', 'ypbind', 'onestart'], check=False)
        if ypbind.returncode != 0:
            await self.__set_state(DSStatus['FAULTED'])
            raise CallError(f'ypbind failed: {ypbind.stderr.decode()}')

        await self.__set_state(DSStatus['HEALTHY'])
        await self.middleware.call('nis.cache_fill')
        return True

    @private
    async def started(self):
        """
        If for some reason, the status check returns false, but NIS is enabled
        set the NIS_state value to FAULTED.
        The return code from ypwhich is not a reliable health indicator.
        """
        nis = await self.middleware.call('nis.config')
        ypwhich = await run(['/usr/bin/ypwhich'], check=False)
        if ypwhich.returncode != 0:
            if nis['enable']:
                await self.__set_state(DSStatus['FAULTED'])
            return False
        if ypwhich.stderr:
            await self.__set_state(DSStatus['FAULTED'])
            raise CallError(f'NIS status check returned [{ypwhich.stderr.decode().strip()}]. Setting state to FAULTED.')

        await self.__set_state(DSStatus['HEALTHY'])
        return True

    @private
    async def stop(self, force=False):
        """
        Remove NIS_state entry entirely after stopping ypbind. This is so that
        the 'enable' checkbox becomes the sole source of truth regarding a service's state
        when it is disabled.
        """
        state = await self.get_state()
        if not force:
            if state in ['LEAVING', 'JOINING']:
                raise CallError(f'Current state of NIS service is: [{state}]. Wait until operation completes.', errno.EBUSY)

        await self.__set_state(DSStatus['LEAVING'])
        await self.middleware.call('nis.update', {'enable': False})
        ypbind = await run(['/usr/sbin/service', 'ypbind', 'onestop'], check=False)
        if ypbind.returncode != 0:
            await self.__set_state(DSStatus['FAULTED'])
            raise CallError(f'ypbind failed to stop: [{ypbind.stderr.decode()}]')

        await self.middleware.call('cache.pop', 'NIS_State')
        await self.middleware.call('etc.generate', 'rc')
        await self.middleware.call('etc.generate', 'pam')
        await self.middleware.call('etc.generate', 'hostname')
        await self.middleware.call('etc.generate', 'nss')
        await self.middleware.call('nis.cache_fill')
        return True

    @job(lock=lambda args: 'nis_cache_fill')
    def cache_fill(self, job):
        cachetool = subprocess.Popen(
            ['/usr/local/www/freenasUI/tools/cachetool.py', 'fill'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
        )
        output = cachetool.communicate()
        if cachetool.returncode != 0:
            self.logger.debug(f'Failed to fill cache: {output[1].decode()}')
            return False

        return True
