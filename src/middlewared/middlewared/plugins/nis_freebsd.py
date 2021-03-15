import asyncio
import errno
import pwd
import grp

from middlewared.schema import accepts, Bool, Dict, List, Str
from middlewared.service import job, private, ConfigService
from middlewared.service_exception import CallError
import middlewared.sqlalchemy as sa
from middlewared.utils import run
from middlewared.plugins.directoryservices import DSStatus


class NISModel(sa.Model):
    __tablename__ = 'directoryservice_nis'

    id = sa.Column(sa.Integer(), primary_key=True)
    nis_domain = sa.Column(sa.String(120))
    nis_servers = sa.Column(sa.String(8192))
    nis_secure_mode = sa.Column(sa.Boolean())
    nis_manycast = sa.Column(sa.Boolean())
    nis_enable = sa.Column(sa.Boolean(), default=False)


class NISService(ConfigService):
    class Config:
        service = "nis"
        datastore = 'directoryservice.nis'
        datastore_extend = "nis.nis_extend"
        datastore_prefix = "nis_"
        cli_namespace = "directory_service.nis"

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

        `enable` enables and starts the NIS service. The NIS service is disabled when this
        value is changed to False.
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
    async def set_state(self, state):
        return await self.middleware.call('directoryservices.set_state', {'nis': state.name})

    @accepts()
    async def get_state(self):
        """
        Wrapper function for 'directoryservices.get_state'. Returns only the state of the
        NIS service.
        """
        return (await self.middleware.call('directoryservices.get_state'))['nis']

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

        await self.set_state(DSStatus['JOINING'])
        await self.middleware.call('datastore.update', 'directoryservice.nis', nis['id'], {'nis_enable': True})
        await self.middleware.call('etc.generate', 'rc')
        await self.middleware.call('etc.generate', 'pam')
        await self.middleware.call('etc.generate', 'hostname')
        await self.middleware.call('etc.generate', 'nss')
        await self.middleware.call('etc.generate', 'user')
        setnisdomain = await run(['/bin/domainname', nis['domain']], check=False)
        if setnisdomain.returncode != 0:
            await self.set_state(DSStatus['FAULTED'])
            raise CallError(f'Failed to set NIS Domain to [{nis["domain"]}]: {setnisdomain.stderr.decode()}')

        ypbind = await run(['/usr/sbin/service', 'ypbind', 'onestart'], check=False)
        if ypbind.returncode != 0:
            await self.set_state(DSStatus['FAULTED'])
            raise CallError(f'ypbind failed: {ypbind.stderr.decode()}')

        await self.set_state(DSStatus['HEALTHY'])
        self.logger.debug(f'NIS service successfully started. Setting state to HEALTHY.')
        await self.middleware.call('nis.fill_cache')
        return True

    @private
    async def __ypwhich(self):
        """
        The return code from ypwhich is not a reliable health indicator. For example, RPC failure will return 0.
        There are edge cases where ypwhich can hang when NIS is misconfigured.
        """
        ypwhich = await run(['/usr/bin/ypwhich'], check=False)

        if ypwhich.stderr:
            raise CallError(f'NIS status check returned [{ypwhich.stderr.decode().strip()}]. Setting state to FAULTED.')
        return True

    @private
    async def started(self):
        ret = False
        if not (await self.config())['enable']:
            return ret

        """
        Initialize state to "JOINING" until after booted.
        """
        if not await self.middleware.call('system.ready'):
            await self.set_state(DSStatus['JOINING'])
            return True

        try:
            ret = await asyncio.wait_for(self.__ypwhich(), timeout=5.0)
        except asyncio.TimeoutError:
            raise CallError('nis.started check timed out after 5 seconds.')

        try:
            cached_state = await self.middleware.call('cache.get', 'DS_STATE')

            if cached_state['nis'] != 'HEALTHY':
                await self.set_state(DSStatus['HEALTHY'])
        except KeyError:
            await self.set_state(DSStatus['HEALTHY'])

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

        await self.set_state(DSStatus['LEAVING'])
        await self.middleware.call('datastore.update', 'directoryservice.nis', nis['id'], {'nis_enable': False})

        ypbind = await run(['/usr/sbin/service', 'ypbind', 'onestop'], check=False)
        if ypbind.returncode != 0:
            await self.set_state(DSStatus['FAULTED'])
            errmsg = ypbind.stderr.decode().strip()
            if 'ypbind not running' not in errmsg:
                raise CallError(f'ypbind failed to stop: [{ypbind.stderr.decode().strip()}]')

        await self.middleware.call('cache.pop', 'NIS_State')
        await self.middleware.call('etc.generate', 'rc')
        await self.middleware.call('etc.generate', 'pam')
        await self.middleware.call('etc.generate', 'hostname')
        await self.middleware.call('etc.generate', 'nss')
        await self.middleware.call('etc.generate', 'user')
        await self.set_state(DSStatus['DISABLED'])
        self.logger.debug(f'NIS service successfully stopped. Setting state to DISABLED.')
        return True

    @private
    @job(lock=lambda args: 'fill_nis_cache')
    def fill_cache(self, job, force=False):
        user_next_index = group_next_index = 200000000
        if self.middleware.call_sync('cache.has_key', 'NIS_cache') and not force:
            raise CallError('NIS cache already exists. Refusing to generate cache.')

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

            cache_data['users'].append({u.pw_name: {
                'id': user_next_index,
                'uid': u.pw_uid,
                'username': u.pw_name,
                'unixhash': None,
                'smbhash': None,
                'group': {},
                'home': '',
                'shell': '',
                'full_name': u.pw_gecos,
                'builtin': False,
                'email': '',
                'password_disabled': False,
                'locked': False,
                'sudo': False,
                'sudo_nopasswd': False,
                'sudo_commands': [],
                'microsoft_account': False,
                'attributes': {},
                'groups': [],
                'sshpubkey': None,
                'local': False
            }})
            user_next_index += 1

        for g in grp_list:
            is_local_user = True if g.gr_gid in local_gid_list else False
            if is_local_user:
                continue

            cache_data['groups'].append({g.gr_name: {
                'id': group_next_index,
                'gid': g.gr_gid,
                'group': g.gr_name,
                'builtin': False,
                'sudo': False,
                'sudo_nopasswd': False,
                'sudo_commands': [],
                'users': [],
                'local': False
            }})
            group_next_index += 1

        self.middleware.call_sync('cache.put', 'NIS_cache', cache_data)
        self.middleware.call_sync('dscache.backup')

    @private
    async def get_cache(self):
        if not await self.middleware.call('cache.has_key', 'NIS_cache'):
            await self.middleware.call('nis.fill_cache')
            self.logger.debug('cache fill is in progress.')
            return {'users': [], 'groups': []}

        return await self.middleware.call('cache.get', 'NIS_cache')
