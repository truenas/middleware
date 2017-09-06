from middlewared.schema import accepts, Bool
from middlewared.service import ConfigService, private
from middlewared.utils import run

import asyncio
import os
import shutil

SYSDATASET_PATH = '/var/db/system'


class SystemDatasetService(ConfigService):

    @accepts()
    async def config(self):
        return await self.middleware.call('datastore.config', 'system.systemdataset', {'prefix': 'sys_', 'extend': 'systemdataset.config_extend'})

    @private
    async def config_extend(self, config):

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
            if await self.middleware.call('notifier.failover_node') == 'B':
                config['uuid'] = config['uuid_b']

        return config

    @accepts(Bool('mount', default=True))
    @private
    async def setup(self, mount):
        if not await self.middleware.call('system.is_freenas'):
            if await self.middleware.call('notifier.failover_status') == 'BACKUP':
                try:
                    os.unlink(SYSDATASET_PATH)
                except OSError:
                    pass
                return

        config = await self.config()
        if not config['basename']:
            if os.path.exists(SYSDATASET_PATH):
                try:
                    os.rmdir(SYSDATASET_PATH)
                except Exception:
                    self.logger.debug('Failed to remove system dataset dir', exc_info=True)
            return config

        if not config['is_decrypted']:
            return

        datasets = [config['basename']]
        for sub in (
            'cores', 'samba4', f'syslog-{config["uuid"]}',
            f'rrd-{config["uuid"]}', f'configs-{config["uuid"]}',
        ):
            datasets.append(f'{config["basename"]}/{sub}')

        createdds = False
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

        if createdds:
            # There is no need to wait this to finish
            asyncio.ensure_future(self.middleware.call('service.restart', 'collectd'))

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

            datasets_mountpoints = [
                (datasets[0], SYSDATASET_PATH)
            ] + [
                (d, f'{SYSDATASET_PATH}/{d.rsplit("/", 1)[-1]}')
                for d in datasets[1:]
            ]
            for dataset, mountpoint in datasets_mountpoints:
                if os.path.ismount(mountpoint):
                    continue
                if not os.path.isdir(mountpoint):
                    os.mkdir(mountpoint)
                await run('mount', '-t', 'zfs', dataset, mountpoint, check=False)

            corepath = f'{SYSDATASET_PATH}/cores'
            if os.path.exists(corepath):
                # FIXME: sysctl module not working
                await run('sysctl', f"kern.corefile='{corepath}/%N.core'")
                os.chmod(corepath, 0o775)

            await self.__nfsv4link()

        return config

    @private
    def path(self):
        if not os.path.exists(SYSDATASET_PATH):
            return None

        if not os.path.ismount(SYSDATASET_PATH):
            return None

        return SYSDATASET_PATH

    async def __nfsv4link(self):
        syspath = self.path()
        if not syspath:
            return None

        restartfiles = ["/var/db/nfs-stablerestart", "/var/db/nfs-stablerestart.bak"]
        if not await self.middleware.call('system.is_freenas') and await self.middleware.call('notifier.failover_status') == 'BACKUP':
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
