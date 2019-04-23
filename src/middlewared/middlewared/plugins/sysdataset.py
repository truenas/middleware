from middlewared.schema import accepts, Bool, Dict, Str
from middlewared.service import CallError, ConfigService, ValidationErrors, job, private
from middlewared.utils import Popen, run

import asyncio
import errno
import os
import shutil
import uuid

SYSDATASET_PATH = '/var/db/system'


class SystemDatasetService(ConfigService):

    class Config:
        datastore = 'system.systemdataset'
        datastore_extend = 'systemdataset.config_extend'
        datastore_prefix = 'sys_'

    @private
    async def config_extend(self, config):

        # Treat empty system dataset pool as freenas-boot
        if not config['pool']:
            config['pool'] = 'freenas-boot'
        # Add `is_decrypted` dynamic attribute
        if config['pool'] == 'freenas-boot':
            config['is_decrypted'] = True
        else:
            pool = await self.middleware.call('pool.query', [('name', '=', config['pool'])])
            if pool:
                config['is_decrypted'] = pool[0]['is_decrypted']
            else:
                config['is_decrypted'] = False

        if config['is_decrypted']:
            config['basename'] = f'{config["pool"]}/.system'
        else:
            config['basename'] = None

        # Make `uuid` point to the uuid of current node
        config['uuid_a'] = config['uuid']
        if not await self.middleware.call('system.is_freenas'):
            if await self.middleware.call('failover.node') == 'B':
                config['uuid'] = config['uuid_b']

        if not config['uuid']:
            config['uuid'] = uuid.uuid4().hex
            if not await self.middleware.call('system.is_freenas') and await self.middleware.call('failover.node') == 'B':
                attr = 'uuid_b'
                config[attr] = config['uuid']
            else:
                attr = 'uuid'
            await self.middleware.call('datastore.update', 'system.systemdataset', config['id'], {f'sys_{attr}': config['uuid']})

        config['syslog'] = config.pop('syslog_usedataset')

        if not os.path.exists(SYSDATASET_PATH) or not os.path.ismount(SYSDATASET_PATH):
            config['path'] = None
        else:
            config['path'] = SYSDATASET_PATH

        return config

    @accepts(Dict(
        'sysdataset_update',
        Str('pool', null=True),
        Str('pool_exclude', null=True),
        Bool('syslog'),
        update=True
    ))
    @job(lock='sysdataset_update')
    async def do_update(self, job, data):
        """
        Update System Dataset Service Configuration.

        `pool` is the name of a valid pool configured in the system which will be used to host the system dataset.

        `pool_exclude` can be specified to make sure that we don't place the system dataset on that pool if `pool`
        is not provided.
        """
        config = await self.config()

        new = config.copy()
        new.update(data)

        verrors = ValidationErrors()
        if new['pool'] and new['pool'] != 'freenas-boot':
            pool = await self.middleware.call('pool.query', [['name', '=', new['pool']]])
            if not pool:
                verrors.add(
                    'sysdataset_update.pool',
                    f'Pool "{new["pool"]}" not found',
                    errno.ENOENT
                )
            elif pool[0]['encrypt'] == 2:
                # This will cover two cases - passphrase being set for a pool and that it might be locked as well
                verrors.add(
                    'sysdataset_update.pool',
                    f'Pool "{new["pool"]}" has an encryption passphrase set. '
                    'The system dataset cannot be placed on this pool.'
                )
        elif not new['pool']:
            for pool in await self.middleware.call(
                'pool.query', [
                    ['encrypt', '!=', 2]
                ]
            ):
                if data.get('pool_exclude') == pool['name']:
                    continue
                new['pool'] = pool['name']
                break
            else:
                # If a data pool could not be found, reset it to blank
                # Which will eventually mean its back to freenas-boot (temporarily)
                new['pool'] = ''
        verrors.check()

        new['syslog_usedataset'] = new['syslog']

        update_dict = new.copy()
        for key in ('is_decrypted', 'basename', 'uuid_a', 'syslog', 'path', 'pool_exclude'):
            update_dict.pop(key, None)

        await self.middleware.call(
            'datastore.update',
            'system.systemdataset',
            config['id'],
            update_dict,
            {'prefix': 'sys_'}
        )

        new = await self.config()

        if config['pool'] != new['pool']:
            await self.migrate(config['pool'], new['pool'])

        await self.setup()

        if config['syslog'] != new['syslog']:
            await self.middleware.call('service.restart', 'syslogd')

        return await self.config()

    @accepts(Bool('mount', default=True), Str('exclude_pool', default=None, null=True))
    @private
    async def setup(self, mount, exclude_pool=None):
        # We default kern.corefile value
        await run('sysctl', "kern.corefile='/var/tmp/%N.core'")

        config = await self.config()
        dbconfig = await self.middleware.call(
            'datastore.config', self._config.datastore, {'prefix': self._config.datastore_prefix}
        )

        if (
            not await self.middleware.call('system.is_freenas') and
            await self.middleware.call('failover.status') == 'BACKUP' and
            config.get('basename') and config['basename'] != 'freenas-boot/.system'
        ):
            try:
                os.unlink(SYSDATASET_PATH)
            except OSError:
                pass
            return

        # If the system dataset is configured in a data pool we need to make sure it exists.
        # In case it does not we need to use another one.
        if config['pool'] != 'freenas-boot' and not await self.middleware.call(
            'pool.query', [('name', '=', config['pool'])]
        ):
            job = await self.middleware.call('systemdataset.update', {
                'pool': None, 'pool_exclude': exclude_pool,
            })
            await job.wait()
            if job.error:
                raise CallError(job.error)
            return

        # If we dont have a pool configure in the database try to find the first data pool
        # to put it on.
        if not dbconfig['pool']:
            pool = None
            for p in await self.middleware.call(
                'pool.query', [('encrypt', '!=', '2')], {'order_by': ['encrypt']}
            ):
                if exclude_pool and p['name'] == exclude_pool:
                    continue
                if p['is_decrypted']:
                    pool = p
                    break
            if pool:
                job = await self.middleware.call('systemdataset.update', {'pool': pool['name']})
                await job.wait()
                if job.error:
                    raise CallError(job.error)
                return

        if not config['basename']:
            if os.path.exists(SYSDATASET_PATH):
                try:
                    os.rmdir(SYSDATASET_PATH)
                except Exception:
                    self.logger.debug('Failed to remove system dataset dir', exc_info=True)
            return config

        if not config['is_decrypted']:
            return

        if await self.__setup_datasets(config['pool'], config['uuid']):
            # There is no need to wait this to finish
            # Restarting rrdcached will ensure that we start/restart collectd as well
            asyncio.ensure_future(self.middleware.call('service.restart', 'rrdcached'))

        if not os.path.isdir(SYSDATASET_PATH):
            if os.path.exists(SYSDATASET_PATH):
                os.unlink(SYSDATASET_PATH)
            os.mkdir(SYSDATASET_PATH)

        aclmode = await self.middleware.call('zfs.dataset.query', [('id', '=', config['basename'])])
        if aclmode and aclmode[0]['properties']['aclmode']['value'] == 'restricted':
            await self.middleware.call(
                'zfs.dataset.update',
                config['basename'],
                {'properties': {'aclmode': {'value': 'passthrough'}}},
            )

        if mount:

            await self.__mount(config['pool'], config['uuid'])

            corepath = f'{SYSDATASET_PATH}/cores'
            if os.path.exists(corepath):
                # FIXME: sysctl module not working
                await run('sysctl', f"kern.corefile='{corepath}/%N.core'")
                os.chmod(corepath, 0o775)

            await self.__nfsv4link(config)

        return config

    async def __setup_datasets(self, pool, uuid):
        """
        Make sure system datasets for `pool` exist and have the right mountpoint property
        """
        createdds = False
        datasets = [i[0] for i in self.__get_datasets(pool, uuid)]
        datasets_prop = {i['id']: i['properties'].get('mountpoint') for i in await self.middleware.call('zfs.dataset.query', [('id', 'in', datasets)])}
        for dataset in datasets:
            mountpoint = datasets_prop.get(dataset)
            if mountpoint and mountpoint['value'] != 'legacy':
                await self.middleware.call(
                    'zfs.dataset.update',
                    dataset,
                    {'properties': {'mountpoint': {'value': 'legacy'}}},
                )
            elif not mountpoint:
                await self.middleware.call('zfs.dataset.create', {
                    'name': dataset,
                    'properties': {'mountpoint': 'legacy'},
                })
                createdds = True
        return createdds

    async def __mount(self, pool, uuid, path=SYSDATASET_PATH):
        for dataset, name in self.__get_datasets(pool, uuid):
            if name:
                mountpoint = f'{path}/{name}'
            else:
                mountpoint = path
            if os.path.ismount(mountpoint):
                continue
            if not os.path.isdir(mountpoint):
                os.mkdir(mountpoint)
            await run('mount', '-t', 'zfs', dataset, mountpoint, check=True)

    async def __umount(self, pool, uuid):
        for dataset, name in reversed(self.__get_datasets(pool, uuid)):
            await run('umount', '-f', dataset, check=False)

    def __get_datasets(self, pool, uuid):
        return [(f'{pool}/.system', '')] + [
            (f'{pool}/.system/{i}', i) for i in [
                'cores', 'samba4', f'syslog-{uuid}',
                f'rrd-{uuid}', f'configs-{uuid}', 'webui',
            ]
        ]

    async def __nfsv4link(self, config):
        syspath = config['path']
        if not syspath:
            return None

        restartfiles = ["/var/db/nfs-stablerestart", "/var/db/nfs-stablerestart.bak"]
        if not await self.middleware.call('system.is_freenas') and await self.middleware.call('failover.status') == 'BACKUP':
            return None

        for item in restartfiles:
            if os.path.exists(item):
                if os.path.isfile(item) and not os.path.islink(item):
                    # It's an honest to goodness file, this shouldn't ever happen...but
                    path = os.path.join(syspath, os.path.basename(item))
                    if not os.path.isfile(path):
                        # there's no file in the system dataset, so copy over what we have
                        # being careful to nuke anything that is there that happens to
                        # have the same name.
                        if os.path.exists(path):
                            shutil.rmtree(path)
                        shutil.copy(item, path)
                    # Nuke the original file and create a symlink to it
                    # We don't need to worry about creating the file on the system dataset
                    # because it's either been copied over, or was already there.
                    os.unlink(item)
                    os.symlink(path, item)
                elif os.path.isdir(item):
                    # Pathological case that should never happen
                    shutil.rmtree(item)
                    self.__createlink(syspath, item)
                else:
                    if not os.path.exists(os.readlink(item)):
                        # Dead symlink or some other nastiness.
                        shutil.rmtree(item)
                        self.__createlink(syspath, item)
            else:
                # We can get here if item is a dead symlink
                if os.path.islink(item):
                    os.unlink(item)
                self.__createlink(syspath, item)

    def __createlink(self, syspath, item):
        path = os.path.join(syspath, os.path.basename(item))
        if not os.path.isfile(path):
            if os.path.exists(path):
                # There's something here but it's not a file.
                shutil.rmtree(path)
            open(path, 'w').close()
        os.symlink(path, item)

    @private
    async def migrate(self, _from, _to):

        config = await self.config()

        await self.__setup_datasets(_to, config['uuid'])

        if _from:
            path = '/tmp/system.new'
            if not os.path.exists('/tmp/system.new'):
                os.mkdir('/tmp/system.new')
        else:
            path = SYSDATASET_PATH
        await self.__mount(_to, config['uuid'], path=path)

        restart = ['collectd', 'rrdcached', 'syslogd']

        if await self.middleware.call('service.started', 'cifs'):
            restart.insert(0, 'cifs')

        try:
            for i in restart:
                await self.middleware.call('service.stop', i)

            if _from:
                cp = await run('rsync', '-az', f'{SYSDATASET_PATH}/', '/tmp/system.new', check=False)
                if cp.returncode == 0:
                    await self.__umount(_from, config['uuid'])
                    await self.__umount(_to, config['uuid'])
                    await self.__mount(_to, config['uuid'], SYSDATASET_PATH)
                    proc = await Popen(f'zfs list -H -o name {_from}/.system|xargs zfs destroy -r', shell=True)
                    await proc.communicate()

                os.rmdir('/tmp/system.new')
        finally:

            restart.reverse()
            for i in restart:
                await self.middleware.call('service.start', i)

        await self.__nfsv4link(config)


async def pool_post_import(middleware, pool):
    """
    On pool import we may need to reconfigure system dataset.
    """
    await middleware.call('systemdataset.setup')


async def setup(middleware):
    middleware.register_hook('pool.post_import_pool', pool_post_import, sync=True)
