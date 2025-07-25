import asyncio
import base64
import errno
import json
import itertools
import logging
import os
import shutil
import stat
import time
from functools import partial

from middlewared.api import api_method
from middlewared.api.current import (
    FailoverBecomePassiveArgs,
    FailoverBecomePassiveResult,
    FailoverEntry,
    FailoverGetIpsArgs,
    FailoverGetIpsResult,
    FailoverLicensedArgs,
    FailoverLicensedResult,
    FailoverNodeArgs,
    FailoverNodeResult,
    FailoverStatusArgs,
    FailoverStatusResult,
    FailoverSyncFromPeerArgs,
    FailoverSyncFromPeerResult,
    FailoverSyncToPeerArgs,
    FailoverSyncToPeerResult,
    FailoverUpdateArgs,
    FailoverUpdateResult,
    FailoverUpgradeArgs,
    FailoverUpgradeResult,
)
from middlewared.auth import TruenasNodeSessionManagerCredentials
from middlewared.schema import NOT_PROVIDED
from middlewared.service import (
    job,
    private,
    CallError,
    ConfigService,
    ValidationError,
    ValidationErrors
)
import middlewared.sqlalchemy as sa
from middlewared.plugins.auth import AuthService
from middlewared.plugins.config import FREENAS_DATABASE
from middlewared.plugins.failover_.zpool_cachefile import ZPOOL_CACHE_FILE, ZPOOL_CACHE_FILE_OVERWRITE
from middlewared.plugins.failover_.configure import HA_LICENSE_CACHE_KEY
from middlewared.plugins.failover_.enums import DisabledReasonsEnum
from middlewared.plugins.failover_.remote import NETWORK_ERRORS
from middlewared.plugins.system.reboot import RebootReason
from middlewared.plugins.update_.install import STARTING_INSTALLER
from middlewared.plugins.update_.update import SYSTEM_UPGRADE_REBOOT_REASON
from middlewared.plugins.update_.utils import DOWNLOAD_UPDATE_FILE
from middlewared.plugins.update_.utils_linux import mount_update
from middlewared.utils.contextlib import asyncnullcontext

ENCRYPTION_CACHE_LOCK = asyncio.Lock()

logger = logging.getLogger('failover')


class FailoverModel(sa.Model):
    __tablename__ = 'system_failover'

    id = sa.Column(sa.Integer(), primary_key=True)
    disabled = sa.Column(sa.Boolean(), default=False)
    master_node = sa.Column(sa.String(1))
    timeout = sa.Column(sa.Integer(), default=0)


class FailoverService(ConfigService):

    LAST_STATUS = None
    LAST_DISABLEDREASONS = None

    class Config:
        datastore = 'system.failover'
        datastore_extend = 'failover.failover_extend'
        cli_private = True
        role_prefix = 'FAILOVER'
        entry = FailoverEntry

    @private
    async def failover_extend(self, data):
        data['master'] = await self.middleware.call('failover.node') == data.pop('master_node')
        return data

    @api_method(
        FailoverUpdateArgs,
        FailoverUpdateResult,
        audit='Failover config update',
    )
    async def do_update(self, data):
        """Update failover configuration."""
        master = data.pop('master', NOT_PROVIDED)
        old = await self.middleware.call('datastore.config', 'system.failover')
        new = old.copy()
        new.update(data)
        if master is NOT_PROVIDED:
            # The node making the call is the one we want to make MASTER by default
            new['master_node'] = await self.middleware.call('failover.node')
        else:
            new['master_node'] = await self._master_node(master)

        verrors = ValidationErrors()
        if new['disabled'] is False:
            if not await self.middleware.call('interface.query', [('failover_critical', '=', True)]):
                verrors.add(
                    'failover_update.disabled',
                    'You need at least one critical interface to enable failover.',
                )
        verrors.check()

        await self.middleware.call('datastore.update', 'system.failover', new['id'], new)

        if new['disabled']:
            if new['master_node'] == await self.middleware.call('failover.node'):
                await self.middleware.call('failover.force_master')
            else:
                await self.middleware.call('failover.call_remote', 'failover.force_master')

        return await self.config()

    async def _master_node(self, master):
        node = await self.middleware.call('failover.node')
        if node == 'A':
            if master:
                return 'A'
            else:
                return 'B'
        elif node == 'B':
            if master:
                return 'B'
            else:
                return 'A'
        else:
            raise CallError('Unable to change node state in MANUAL mode')

    @api_method(
        FailoverLicensedArgs,
        FailoverLicensedResult,
        authorization_required=False,
    )
    def licensed(self):
        """Checks whether this instance is licensed as a HA unit"""
        try:
            is_ha = self.middleware.call_sync('cache.get', HA_LICENSE_CACHE_KEY)
        except KeyError:
            is_ha = False
            if (info := self.middleware.call_sync('system.license')) is not None and info['system_serial_ha']:
                is_ha = True
                self.middleware.call_sync('cache.put', HA_LICENSE_CACHE_KEY, is_ha)

        return is_ha

    @private
    async def ha_mode(self):
        # NOTE: `failover.enclosure.detect` is cached
        return await self.middleware.call('failover.enclosure.detect')

    @private
    async def hardware(self):
        """
        Returns the hardware type for an HA system.
          ECHOSTREAM (z-series)
          ECHOWARP (m-series)
          LAJOLLA2 (f-series)
          SUBLIGHT (h-series)
          PUMA (x-series)
          BHYVE (HA VMs for CI)
          IXKVM (HA VMs (on KVM) for CI)
          MANUAL (everything else)
        """
        return (await self.ha_mode())[0]

    @api_method(
        FailoverNodeArgs,
        FailoverNodeResult,
        roles=['FAILOVER_READ']
    )
    async def node(self):
        """
        Returns the slot position in the chassis that
        the controller is located.
          A - First node
          B - Seconde Node
          MANUAL - slot position in chassis could not be determined
        """
        return (await self.ha_mode())[1]

    @private
    async def internal_interfaces(self):
        """
        This is a p2p ethernet connection on HA systems.
        """
        ints = await self.middleware.call('failover.internal_interface.detect')
        return list(ints)

    @api_method(
        FailoverStatusArgs,
        FailoverStatusResult,
        pass_app=True,
        roles=['FAILOVER_READ']
    )
    async def status(self, app):
        """
        Get the current HA status.

        Returns:
            MASTER
            BACKUP
            ELECTING
            IMPORTING
            ERROR
            SINGLE
        """
        status = await self._status(app)
        if status != self.LAST_STATUS:
            self.LAST_STATUS = status
            self.middleware.send_event('failover.status', 'CHANGED', fields={'status': status})

        return status

    async def _status(self, app):
        try:
            status = await self.middleware.call('cache.get', 'failover_status')
        except KeyError:
            status = await self.middleware.call('failover.status.get_local', app)
            if status:
                await self.middleware.call('cache.put', 'failover_status', status, 300)

        if status:
            return status

        try:
            # timeout of 5 seconds is necessary here since this could be called
            # when the other node has been forcefully rebooted so the websocket
            # connection is "up" but the default TCP window hasn't elapsed so
            # the connection remains alive. Without the timeout, this could take
            # 20+ seconds to return which is unacceptable during a failover event.
            remote_imported = await self.middleware.call(
                'failover.call_remote', 'zfs.pool.query_imported_fast', [], {'timeout': 5}
            )
            if len(remote_imported) <= 1:
                # getting here means we dont have a pool and neither does remote node
                return 'ERROR'
            else:
                # Other node has the pool (excluding boot pool)
                return 'BACKUP'
        except Exception as e:
            # Anything other than ClientException is unexpected and should be logged
            if not isinstance(e, CallError):
                self.logger.warning('Failed checking failover status', exc_info=True)
            return 'UNKNOWN'

    @private
    async def status_refresh(self):
        await self.middleware.call('cache.pop', 'failover_status')
        # Kick a new status so it may be ready on next user call
        await self.middleware.call('failover.status')
        await self.middleware.call('failover.disabled.reasons')

    @private
    def in_progress(self):
        """
        Returns True if there is an ongoing failover event.
        """
        event = self.middleware.call_sync(
            'core.get_jobs', [
                ('method', 'in', [
                    'failover.events.vrrp_master',
                    'failover.events.vrrp_backup'
                ]),
                ('state', 'in', ('RUNNING', 'WAITING')),
            ]
        )
        return bool(event)

    @api_method(
        FailoverGetIpsArgs,
        FailoverGetIpsResult,
        roles=['FAILOVER_READ']
    )
    async def get_ips(self):
        """Get a list of IPs for which the webUI can be accessed."""
        return await self.middleware.call('system.general.get_ui_urls')

    @api_method(
        FailoverBecomePassiveArgs,
        FailoverBecomePassiveResult,
        audit='Failover become passive',
        roles=['FAILOVER_WRITE']
    )
    def become_passive(self):
        """
        This method is only called manually by the end-user so we fully expect that they
        know what they're doing. Furthermore, this method will only run if failover has NOT
        been administratively disabled. The reason why we only allow this in that scenario
        is because the failover logic (on the other node) will ignore any failover "event"
        that comes in if failover has been administratively disabled. This immediately causes
        the HA system to go into a "faulted" state because the other node will get the VIPs
        but it will not import the zpool and it will not start fenced. Only way out of that
        situation is to manually fix things (import zpool, migrate VIPs, start fenced, etc).

        NOTE: The only "safe" way to "become passive" is to use the STCNITH method (similar to STONITH).
        (i.e. Shoot The Current Node In The Head)

        This ensures that the current node gets out of the way _completely_ so there is no chance
        of the zpool being imported at the same time on both nodes (which can ultimately end in data corruption).
        """
        if self.middleware.call_sync('failover.config')['disabled'] is True:
            raise ValidationError('failover.become_passive', 'Failover must be enabled.')
        else:
            try:
                # have to enable the "magic" sysrq triggers
                with open('/proc/sys/kernel/sysrq', 'w') as f:
                    f.write('1')

                # now violently reboot
                with open('/proc/sysrq-trigger', 'w') as f:
                    f.write('b')
            except Exception:
                # yeah...this isn't good
                self.logger.error('Unexpected failure in failover.become_passive', exc_info=True)
            finally:
                # this shouldn't be reached but better safe than sorry
                os.system('shutdown -r now')

    @private
    async def force_master(self):
        """
        Force this controller to become MASTER, if it's not already.
        """
        if not await self.middleware.call('system.is_enterprise'):
            return False

        if await self.middleware.call('failover.status') == 'MASTER':
            return False

        crit_ints = [i for i in await self.middleware.call('interface.query') if i.get('failover_critical', False)]
        if crit_ints:
            await self.middleware.call('failover.events.event', crit_ints[0]['name'], 'forcetakeover')
            return True
        else:
            # if there are no interfaces marked critical for failover and this method was
            # still called, then we can at least start fenced to reserve the disks
            rc = await self.middleware.call('failover.fenced.start', True)
            return not rc if rc != 6 else bool(rc)  # 6 means already running

    @api_method(
        FailoverSyncToPeerArgs,
        FailoverSyncToPeerResult,
        roles=['FAILOVER_WRITE'],
    )
    def sync_to_peer(self, options):
        """
        Sync database and files to the other controller.

        `reboot` as true will reboot the other controller after syncing.
        """
        standby = ' standby controller.'

        self.logger.debug('Persisting interface link addresses')
        self.middleware.call_sync('interface.persist_link_addresses')

        self.logger.debug('Pulling system dataset UUID from' + standby)
        self.middleware.call_sync('systemdataset.ensure_standby_uuid')

        self.logger.debug('Syncing database to' + standby)
        self.middleware.call_sync('failover.datastore.send')

        self.logger.debug('Syncing cached encryption keys to' + standby)
        self.middleware.call_sync('failover.sync_keys_to_remote_node')

        self.logger.debug('Syncing zpool cachefile, license, pwenc and authorized_keys files to' + standby)
        self.send_small_file('/data/license')
        self.send_small_file('/data/pwenc_secret')
        self.send_small_file('/home/admin/.ssh/authorized_keys')
        self.send_small_file('/home/truenas_admin/.ssh/authorized_keys')
        self.send_small_file('/root/.ssh/authorized_keys')
        self.send_small_file(ZPOOL_CACHE_FILE, ZPOOL_CACHE_FILE_OVERWRITE)
        self.middleware.call_sync('failover.call_remote', 'failover.zpool.cachefile.setup', ['SYNC'])

        self.middleware.call_sync(
            'failover.call_remote', 'core.call_hook', ['config.on_upload', [FREENAS_DATABASE]],
            {'timeout': 300},  # Give more time for potential initrd update
        )

        # need to make sure the license information is updated on the standby node since
        # it's cached in memory
        _prev = self.middleware.call_sync('system.license')
        self.middleware.call_sync(
            'failover.call_remote', 'core.call_hook', ['system.post_license_update', [_prev]]
        )

        if options['reboot']:
            self.middleware.call_sync('failover.call_remote', 'system.reboot', ['Failover sync to peer', {'delay': 2}])

    @api_method(
        FailoverSyncFromPeerArgs,
        FailoverSyncFromPeerResult,
        roles=['FAILOVER_WRITE'],
    )
    def sync_from_peer(self):
        """
        Sync database and files from the other controller.
        """
        self.middleware.call_sync('failover.call_remote', 'failover.sync_to_peer')

    @private
    def send_small_file(self, path, dest=None):
        try:
            with open(path, 'rb') as f:
                st = os.fstat(f.fileno())
                if not stat.S_ISREG(st.st_mode):
                    raise CallError(f'{path!r} must be a regular file')

                first = True
                dest = path if dest is None else dest
                opts = {'mode': st.st_mode, 'uid': st.st_uid, 'gid': st.st_gid}
                while True:
                    read = f.read(1024 * 1024 * 10)
                    if not read:
                        break

                    opts.update({'append': not first})
                    self.middleware.call_sync(
                        'failover.call_remote',
                        'filesystem.file_receive',
                        [dest, base64.b64encode(read).decode(), opts]
                    )
                    first = False
        except FileNotFoundError:
            return

    @private
    async def get_disks_local(self):
        try:
            lbd = await self.middleware.call('boot.get_disks')
            return [
                serial for disk, serial in (await self.middleware.call('device.get_disks', False, True)).items()
                if disk not in lbd
            ]
        except Exception:
            self.logger.error('Unhandled exception in get_disks_local', exc_info=True)

    @private
    async def mismatch_nics(self):
        """Determine if NICs match between both controllers."""
        result = {'missing_local': list(), 'missing_remote': list()}
        try:
            local_nics = await self.middleware.call('interface.query')
            local_nonphysical_names = {i['name'] for i in local_nics if i['type'] != 'PHYSICAL'}
            local_physical_mac_to_name = {i['state']['link_address']: i['name']
                                          for i in local_nics
                                          if i['type'] == 'PHYSICAL'}
        except Exception:
            self.logger.error('Unhandled exception querying ifaces on local controller', exc_info=True)
            return result

        try:
            remote_nics = await self.middleware.call(
                'failover.call_remote', 'interface.query', [],
                {'raise_connect_error': False, 'timeout': 2, 'connect_timeout': 2}
            )
        except Exception:
            self.logger.error('Unhandled exception querying ifaces on remote controller', exc_info=True)
        else:
            if remote_nics is not None:
                remote_nonphysical_names = {i['name'] for i in remote_nics if i['type'] != 'PHYSICAL'}
                remote_physical_mac_to_name = {i['state']['link_address']: i['name']
                                               for i in remote_nics
                                               if i['type'] == 'PHYSICAL'}

                # Physical NICs can't be just matched by name, because names can change due to OS kernel upgrades.
                # Match them by hardware addresses instead.
                _local_macs_to_remote_macs = await self.middleware.call('interface.local_macs_to_remote_macs')
                if not _local_macs_to_remote_macs and await self.middleware.call('failover.status') == 'MASTER':
                    # We might have not yet had a successful persist_link_addresses, but we know that now we
                    # can communicate with the remote node, so try again.
                    await self.middleware.call("interface.persist_link_addresses")
                    if _local_macs_to_remote_macs := await self.middleware.call('interface.local_macs_to_remote_macs'):
                        self.logger.debug('Repaired local_macs_to_remote_macs')
                missing_local, missing_remote = mismatch_nics(
                    local_physical_mac_to_name,
                    remote_physical_mac_to_name,
                    _local_macs_to_remote_macs
                )

                missing_local += list(remote_nonphysical_names - local_nonphysical_names)
                missing_remote += list(local_nonphysical_names - remote_nonphysical_names)

                result['missing_local'] = sorted(missing_local)
                result['missing_remote'] = sorted(missing_remote)

        return result

    @private
    async def mismatch_disks(self):
        """On HA systems, the block device names can be different between the controllers.
        Because of this fact, we need to check the serials of each disk which should be the
        same between the controllers.
        """
        result = {'missing_local': list(), 'missing_remote': list()}
        if (ld := await self.get_disks_local()) is not None:
            try:
                rd = await self.middleware.call(
                    'failover.call_remote', 'failover.get_disks_local', [],
                    {'raise_connect_error': False, 'timeout': 2, 'connect_timeout': 2}
                )
            except Exception:
                self.logger.error('Unhandled exception in get_disks_local on remote controller', exc_info=True)
            else:
                if rd is not None:
                    result['missing_local'] = sorted(set(rd) - set(ld))
                    result['missing_remote'] = sorted(set(ld) - set(rd))

        return result

    @private
    @job(lock='failover_dataset_unlock')
    async def unlock_zfs_datasets(self, job, pool_name):
        # Unnlock all (if any) zfs datasets for `pool_name`
        # that we have keys for in the cache or the database.
        zfs_keys = [
            {'name': name, 'passphrase': passphrase}
            for name, passphrase in (await self.encryption_keys())['zfs'].items()
            if name == pool_name or name.startswith(f'{pool_name}/')
        ]
        unlock_job = await self.middleware.call(
            'pool.dataset.unlock', pool_name, {
                'recursive': True,
                'datasets': zfs_keys,
                # Do not waste time handling attachments, failover process will restart services and regenerate configs
                # for us
                'toggle_attachments': False,
            }
        )
        return await job.wrap(unlock_job)

    @private
    async def encryption_keys(self):
        # TODO: remove GELI key since it's
        # not supported in SCALE
        return await self.middleware.call(
            'cache.get_or_put', 'failover_encryption_keys', 0, lambda: {'geli': {}, 'zfs': {}}
        )

    @private
    async def update_encryption_keys(self, options: dict):
        """
        `options` should look like
            {
                'sync_keys': True,
                'pools': [
                    {
                        'name': 'tank',
                        'passphrase': 'blah',
                    },
                ],
                'datasets': [
                    {
                        'name': 'tank/dataset',
                        'passphrase': 'blah',
                    },
                ]
            }
        """
        # TODO: remove `pools` key and `geli` logic
        # since GELI is not supported in SCALE
        options.setdefault('sync_keys', True)
        options.setdefault('pools', [])
        options.setdefault('datasets', [])
        if not options['pools'] and not options['datasets']:
            raise CallError('Please specify pools/datasets to update')

        async with ENCRYPTION_CACHE_LOCK:
            keys = await self.encryption_keys()
            for pool in options['pools']:
                keys['geli'][pool['name']] = pool['passphrase']
            for dataset in options['datasets']:
                keys['zfs'][dataset['name']] = dataset['passphrase']
            await self.middleware.call('cache.put', 'failover_encryption_keys', keys)
            if options['sync_keys']:
                await self.sync_keys_to_remote_node(lock=False)

    @private
    async def remove_encryption_keys(self, options):
        """
        `options` should look like
            {
                'sync_keys': True,
                'pools': ['tank',],
                'datasets': ['tank/dataset',]
            }
        """
        # TODO: remove `pools` key and `geli` logic
        # since GELI is not supported in SCALE
        options.setdefault('sync_keys', True)
        options.setdefault('pools', [])
        options.setdefault('datasets', [])
        if not options['pools'] and not options['datasets']:
            raise CallError('Please specify pools/datasets to remove')

        async with ENCRYPTION_CACHE_LOCK:
            keys = await self.encryption_keys()
            for pool in options['pools']:
                keys['geli'].pop(pool, None)
            for dataset in options['datasets']:
                keys['zfs'] = {
                    k: v for k, v in keys['zfs'].items() if k != dataset and not k.startswith(f'{dataset}/')
                }
            await self.middleware.call('cache.put', 'failover_encryption_keys', keys)
            if options['sync_keys']:
                await self.sync_keys_to_remote_node(lock=False)

    @private
    async def is_single_master_node(self):
        return await self.middleware.call('failover.status') in ('MASTER', 'SINGLE')

    @private
    def upgrade_version(self):
        return 1

    @api_method(
        FailoverUpgradeArgs,
        FailoverUpgradeResult,
        roles=['FAILOVER_WRITE'],
        audit='Failover upgrade',
    )
    @job(lock='failover_upgrade', pipes=['input'], check_pipes=False)
    def upgrade(self, job, options):
        """
        Upgrades both controllers. Files will be downloaded to the
        Active Controller and then transferred to the Standby Controller.
        Upgrade process will start concurrently on both nodes. Once both
        upgrades are applied, the Standby Controller will reboot. This
        job will wait for that job to complete before finalizing.
        """
        if self.middleware.call_sync('failover.status') != 'MASTER':
            raise CallError('Upgrade can only run on Active Controller.')

        if not options['resume']:
            try:
                job.check_pipe('input')
            except ValueError:
                updatefile = False
            else:
                updatefile = True
        else:
            updatefile = options['resume_manual']

        local_path = self.middleware.call_sync('update.get_update_location')
        updatefile_name = 'updatefile.sqsh'
        updatefile_localpath = os.path.join(local_path, updatefile_name)
        if not options['resume'] and updatefile:
            # means manual update file was provided so write it
            # to local storage
            job.set_progress(None, 'Uploading update file')
            os.makedirs(local_path, exist_ok=True)
            with open(updatefile_localpath, 'wb') as f:
                shutil.copyfileobj(job.pipes.input.r, f, 1048576)

        try:
            if not self.middleware.call_sync('failover.call_remote', 'system.ready'):
                raise CallError('Standby Controller is not ready.')

            if not options['resume'] and not updatefile:
                # means no update file was provided so go out to
                # the interwebz and download it
                def download_callback(j):
                    job.set_progress(
                        None, j['progress']['description'] or 'Downloading upgrade files'
                    )

                djob = self.middleware.call_sync('update.download', options['train'], options['version'],
                                                 job_on_progress_cb=download_callback)
                djob.wait_sync(raise_error=True)
                if not djob.result:
                    raise CallError('No updates available.')

            if updatefile:
                effective_updatefile_name = updatefile_name
            else:
                effective_updatefile_name = DOWNLOAD_UPDATE_FILE

            # `truenas-installer` automatically determines new BE dataset name based on the version and existing BE
            # names. As BE names can be different on different controllers, automatic process can't be trusted to
            # choose the same bootenv name on both controllers so we explicitly specify BE name for HA upgrades.
            with mount_update(os.path.join(local_path, effective_updatefile_name)) as mounted:
                with open(os.path.join(mounted, 'manifest.json')) as f:
                    manifest = json.load(f)

                bootenv_name = manifest['version']

            existing_bes = set()
            for i in self.middleware.call_sync('boot.environment.query'):
                existing_bes.add(i['id'])

            try:
                for i in self.middleware.call_sync(
                    'failover.call_remote', 'boot.environment.query'
                ):
                    existing_bes.add(i['id'])
            except CallError as e:
                if e.errno == CallError.ENOMETHOD:
                    for i in self.middleware.call_sync('failover.call_remote', 'bootenv.query'):
                        existing_bes.add(i['name'])
                else:
                    raise

            if bootenv_name in existing_bes:
                for i in itertools.count(1):
                    probe_bootenv_name = f"{bootenv_name}-{i}"
                    if probe_bootenv_name not in existing_bes:
                        bootenv_name = probe_bootenv_name
                        break

            dataset_name = f'{self.middleware.call_sync("boot.pool_name")}/ROOT/{bootenv_name}'

            remote_path = self.middleware.call_sync('failover.call_remote', 'update.get_update_location')

            if not options['resume']:
                # Replicate uploaded or downloaded update it to the standby
                job.set_progress(None, 'Sending files to Standby Controller')
                token = self.middleware.call_sync('failover.call_remote', 'auth.generate_token', [
                    300,  # ttl
                    {},  # Attributes (not required for file uploads)
                    True,  # match origin
                    True,  # single-use (required if STIG enabled)
                ])
                self.middleware.call_sync(
                    'failover.send_file',
                    token,
                    os.path.join(local_path, effective_updatefile_name),
                    os.path.join(remote_path, effective_updatefile_name),
                    {'mode': 0o600}
                )

            local_version = self.middleware.call_sync('system.version')
            remote_version = self.middleware.call_sync('failover.call_remote', 'system.version')

            local_started_installer = False
            local_progress = remote_progress = 0
            local_descr = remote_descr = 'Starting upgrade'

            def callback(j, controller):
                nonlocal local_started_installer, local_progress, remote_progress, local_descr, remote_descr
                if controller == 'LOCAL' and j['progress']['description'] == STARTING_INSTALLER:
                    local_started_installer = True
                if j['state'] not in ['RUNNING', 'SUCCESS']:
                    return
                if controller == 'LOCAL':
                    local_progress = j["progress"]["percent"]
                    local_descr = f'{int(j["progress"]["percent"])}%: {j["progress"]["description"]}'
                else:
                    remote_progress = j["progress"]["percent"]
                    remote_descr = f'{int(j["progress"]["percent"])}%: {j["progress"]["description"]}'
                job.set_progress(
                    min(local_progress, remote_progress),
                    f'Active Controller: {local_descr}\n' + f'Standby Controller: {remote_descr}'
                )

            update_options = {
                'dataset_name': dataset_name,
                'resume': options['resume'],
            }

            if updatefile:
                update_method = 'update.manual'
                update_remote_args = [os.path.join(remote_path, updatefile_name), update_options]
                update_local_args = [updatefile_localpath, update_options]
            else:
                update_method = 'update.update'
                update_remote_args = [update_options]
                update_local_args = [update_options]

            # upgrade the local (active) controller
            ljob = self.middleware.call_sync(
                update_method, *update_local_args,
                job_on_progress_cb=partial(callback, controller='LOCAL')
            )
            # Wait for local installer to pass pre-checks and start the install process itself so that we do not start
            # remote upgrade if a pre-check fails.
            while not local_started_installer:
                try:
                    ljob.wait_sync(raise_error=True, timeout=1)
                except TimeoutError:
                    pass

            if local_version == remote_version:
                # start the upgrade on the remote (standby) controller
                rjob = self.middleware.call_sync(
                    'failover.call_remote', update_method, update_remote_args, {
                        'job_return': True,
                        'callback': partial(callback, controller='REMOTE')
                    }
                )
            else:
                rjob = None

            ljob.wait_sync(raise_error=True)

            remote_boot_id = self.middleware.call_sync('failover.call_remote', 'system.boot_id')

            # check the remote (standby) controller upgrade job
            if rjob:
                rjob.result()

            self.middleware.call_sync(
                'failover.call_remote', 'system.reboot', [SYSTEM_UPGRADE_REBOOT_REASON, {'delay': 5}], {'job': True},
            )
        except Exception:
            raise

        # SCALE is using systemd and at the time of writing this, the
        # DefaultTimeoutStopSec setting hasn't been changed and so
        # defaults to 90 seconds. This means when the system is sent the
        # shutdown signal, all the associated user-space programs are
        # asked to be shutdown. If any of those take longer than 90
        # seconds to respond to SIGTERM then the program is sent SIGKILL.
        # Finally, if after 90 seconds the standby controller is still
        # responding to remote requests then play it safe and assume the
        # reboot failed (this should be rare but my future self will
        # appreciate the fact I wrote this out because of the inevitable
        # complexities of gluster/k8s/vms etc etc for which I predict
        # will exhibit this behavior :P )
        job.set_progress(None, 'Waiting on the Standby Controller to reboot.')
        try:
            retry_time = time.monotonic()
            shutdown_timeout = 90  # seconds
            while time.monotonic() - retry_time < shutdown_timeout:
                self.middleware.call_sync(
                    'failover.call_remote', 'core.ping', [], {'timeout': 5}
                )
                time.sleep(5)
        except CallError:
            pass
        else:
            raise CallError(
                f'Timed out waiting {shutdown_timeout} seconds for the standby controller to reboot',
                errno.ETIMEDOUT
            )

        if not self.upgrade_waitstandby():
            raise CallError(
                'Timed out waiting for the standby controller to upgrade.',
                errno.ETIMEDOUT
            )

        # we captured the `remote_boot_id` up above earlier in the upgrade process.
        # This variable represents a 1-time unique boot id. It's supposed to be different
        # every time the system boots up. If this check is True, then it's safe to say
        # that the remote system never rebooted, therefore, never completing the upgrade
        # process....which isn't good.
        if remote_boot_id == self.middleware.call_sync('failover.call_remote', 'system.boot_id'):
            raise CallError('Standby Controller failed to reboot.')

        self.middleware.call_sync('system.reboot.add_reason', RebootReason.UPGRADE.name, RebootReason.UPGRADE.value)

        return True

    @private
    def upgrade_waitstandby(self, seconds=1200, await_failover=False):
        """
        We will wait up to 20 minutes by default for the Standby Controller to reboot.
        This values come from observation from support of how long a M-series can take.
        """
        retry_time = time.monotonic()
        system_ready = False
        failover_in_progress = True
        while time.monotonic() - retry_time < seconds:
            try:
                if system_ready is False and not self.middleware.call_sync('failover.call_remote', 'system.ready'):
                    time.sleep(5)
                    continue
                else:
                    system_ready = True

                if failover_in_progress is True and self.middleware.call_sync(
                    'failover.call_remote', 'failover.in_progress'
                ):
                    time.sleep(5)
                    continue
                else:
                    failover_in_progress = False

                if self.middleware.call_sync('failover.call_remote', 'failover.status') != 'BACKUP':
                    time.sleep(5)
                    continue

                if await_failover and (DisabledReasonsEnum.REM_FAILOVER_ONGOING.name in
                                       self.middleware.call_sync('failover.disabled.reasons')):
                    time.sleep(5)
                    continue

            except CallError as e:
                if e.errno in NETWORK_ERRORS:
                    time.sleep(5)
                    continue
                raise
            else:
                return True
        return False

    @private
    @job(lock='failover_wait_other_node', lock_queue_size=1)
    def wait_other_node(self, job):
        return self.upgrade_waitstandby(await_failover=True)

    @private
    async def sync_keys_from_remote_node(self):
        """
        Sync ZFS encryption keys from the active node.
        """
        if not await self.middleware.call('failover.licensed'):
            return

        # only sync keys if we're the BACKUP node
        if (await self.middleware.call('failover.status')) != 'BACKUP':
            return

        # make sure we can contact the MASTER node
        try:
            assert (await self.middleware.call('failover.call_remote', 'core.ping')) == 'pong'
        except Exception:
            self.logger.error(
                'Failed to contact active controller when syncing encryption keys', exc_info=True
            )
            return

        try:
            await self.middleware.call('failover.call_remote', 'failover.sync_keys_to_remote_node')
        except Exception:
            self.logger.error(
                'Failed to sync keys from active controller when syncing encryption keys', exc_info=True
            )

    @private
    async def sync_keys_to_remote_node(self, lock=True):
        """
        Sync ZFS encryption keys to the standby node.
        """
        if not await self.middleware.call('failover.licensed'):
            return

        # only sync keys if we're the MASTER node
        if (await self.middleware.call('failover.status')) != 'MASTER':
            return

        # make sure we can contact the BACKUP node
        try:
            assert (await self.middleware.call('failover.call_remote', 'core.ping')) == 'pong'
        except Exception:
            self.logger.error(
                'Failed to contact standby controller when syncing encryption keys', exc_info=True
            )
            return

        async with ENCRYPTION_CACHE_LOCK if lock else asyncnullcontext():
            try:
                keys = await self.encryption_keys()
                await self.middleware.call(
                    'failover.call_remote', 'cache.put', ['failover_encryption_keys', keys]
                )
            except Exception as e:
                await self.middleware.call('alert.oneshot_create', 'FailoverKeysSyncFailed', None)
                self.logger.error('Failed to sync keys with standby controller: %s', str(e), exc_info=True)
            else:
                await self.middleware.call('alert.oneshot_delete', 'FailoverKeysSyncFailed', None)
            try:
                kmip_keys = await self.middleware.call('kmip.kmip_memory_keys')
                await self.middleware.call(
                    'failover.call_remote', 'kmip.update_memory_keys', [kmip_keys]
                )
            except Exception as e:
                await self.middleware.call(
                    'alert.oneshot_create', 'FailoverKMIPKeysSyncFailed', {'error': str(e)}
                )
                self.logger.error(
                    'Failed to sync KMIP keys with standby controller: %s', str(e), exc_info=True
                )
            else:
                await self.middleware.call('alert.oneshot_delete', 'FailoverKMIPKeysSyncFailed', None)


async def ha_permission(middleware, app):
    if not app.authenticated and app.origin.is_ha_connection:
        await AuthService.session_manager.login(app, TruenasNodeSessionManagerCredentials())


async def interface_pre_sync_hook(middleware):
    await middleware.call('failover.internal_interface.pre_sync')


async def hook_license_update(middleware, *args, **kwargs):
    await middleware.call('failover.status_refresh')


async def hook_post_rollback_setup_ha(middleware, *args, **kwargs):
    """
    This hook needs to be run after a NIC rollback operation and before
    an `interfaces.sync` operation on a TrueNAS HA system
    """
    if not await middleware.call('failover.licensed'):
        return

    try:
        await middleware.call('failover.call_remote', 'core.ping')
    except Exception:
        middleware.logger.debug('[HA] Failed to contact standby controller', exc_info=True)
        return

    await middleware.call('failover.datastore.send')

    middleware.logger.debug('[HA] Successfully sent database to standby controller')


async def hook_setup_ha(middleware, *args, **kwargs):
    if not await middleware.call('failover.licensed'):
        return

    if not await middleware.call('interface.query', [('failover_virtual_aliases', '!=', [])]):
        return

    if not await middleware.call('pool.query'):
        return

    # If we have reached this stage make sure status is up to date
    await middleware.call('failover.status_refresh')

    try:
        ha_configured = await middleware.call(
            'failover.call_remote', 'failover.status'
        ) != 'SINGLE'
    except Exception:
        ha_configured = False

    if ha_configured:
        # Perform basic initialization of DLM, in case it is needed by iSCSI ALUA
        middleware.logger.debug('[HA] Initialize DLM')
        await middleware.call('dlm.create')

        # If HA is already configured and failover has been disabled,
        # and we have gotten to this point, then this means a few things could be happening.
        #    1. a new interface is being added
        #    2. an alias is being added to an already configured interface
        #    3. an interface is being modified (changing vhid/ip etc)
        #    4. an interface is being deleted

        # In the event #2 happens listed above, there is a race condition that
        # must be accounted for. When an alias is added to an already configured interface,
        # a CARP event will be triggered and the interface will go from MASTER to INIT->BACKUP->MASTER which
        # generates a devd event that is processed by the failover.event plugin.
        # It takes a few seconds for the kernel to transition the CARP interface from BACKUP->MASTER.
        # However, we refresh the failover.status while this interface is transitioning.
        # This means that failover.status returns 'ERROR'.
        # To work around this we check 2 things:
        #    1. if failover.status == 'MASTER' then we continue
        #    or
        #    2. the node in the chassis is marked as the master_node in the webUI
        #      (because failover has been disabled in the webUI)
        cur_status = await middleware.call('failover.status')
        config = await middleware.call('failover.config')
        if cur_status == 'MASTER' or (config['master'] and config['disabled']):

            # In the event HA is configured and the end-user deletes
            # an interface, we need to sync the database over to the
            # standby node before we call `interface.sync`
            middleware.logger.debug('[HA] Sending database to standby node')
            await middleware.call('failover.datastore.send')

            # Need to send the zpool cachefile to the other node so it matches
            # when a failover event occurs
            middleware.logger.debug('[HA] Sending zpool cachefile to standby node')
            await middleware.call('failover.send_small_file', ZPOOL_CACHE_FILE, ZPOOL_CACHE_FILE_OVERWRITE)
            await middleware.call('failover.call_remote', 'failover.zpool.cachefile.setup', ['SYNC'])

            middleware.logger.debug('[HA] Configuring network on standby node')
            await middleware.call('failover.call_remote', 'interface.sync')

        return

    # when HA is initially setup, we don't synchronize service states to the
    # standby controller. Minimally, however, it's nice to synchronize ssh
    # (if appropriate, of course)
    filters = [('srv_service', '=', 'ssh')]
    ssh_enabled = remote_ssh_started = False
    ssh = await middleware.call('datastore.query', 'services.services', filters)
    if ssh:
        if ssh[0]['srv_enable']:
            ssh_enabled = True
        if await middleware.call('failover.call_remote', 'service.started', ['ssh']):
            remote_ssh_started = True

    middleware.logger.debug('[HA] Setting up')

    middleware.logger.debug('[HA] Synchronizing database and files')
    await middleware.call('failover.sync_to_peer')

    middleware.logger.debug('[HA] Configuring network on standby node')
    await middleware.call('failover.call_remote', 'interface.sync')

    if ssh_enabled and not remote_ssh_started:
        middleware.logger.debug('[HA] Starting SSH on standby node')
        await middleware.call('failover.call_remote', 'service.control', ['START', 'ssh'], {'job': True})

    middleware.logger.debug('[HA] Refreshing failover status')
    await middleware.call('failover.status_refresh')

    middleware.logger.info('[HA] Setup complete')

    middleware.send_event('failover.setup', 'ADDED', fields={})


async def hook_pool_export(middleware, pool=None, *args, **kwargs):
    await middleware.call('failover.remove_encryption_keys', {'pools': [pool]})


async def hook_pool_dataset_unlock(middleware, datasets):
    datasets = [
        {'name': ds['name'], 'passphrase': ds['encryption_key']}
        for ds in datasets if ds['key_format'].upper() == 'PASSPHRASE'
    ]
    if datasets:
        await middleware.call('failover.update_encryption_keys', {'datasets': datasets})


async def hook_pool_dataset_post_create(middleware, dataset_data):
    if dataset_data['encrypted']:
        if str(dataset_data['key_format']).upper() == 'PASSPHRASE':
            await middleware.call(
                'failover.update_encryption_keys', {
                    'datasets': [{'name': dataset_data['name'], 'passphrase': dataset_data['encryption_key']}]
                }
            )
        else:
            kmip = await middleware.call('kmip.config')
            if kmip['enabled'] and kmip['manage_zfs_keys']:
                await middleware.call('failover.sync_keys_to_remote_node')


async def hook_pool_dataset_post_delete_lock(middleware, dataset):
    await middleware.call('failover.remove_encryption_keys', {'datasets': [dataset]})


async def hook_pool_dataset_change_key(middleware, dataset_data):
    if dataset_data['key_format'] == 'PASSPHRASE' or dataset_data['old_key_format'] == 'PASSPHRASE':
        if dataset_data['key_format'] == 'PASSPHRASE':
            await middleware.call(
                'failover.update_encryption_keys', {
                    'datasets': [{'name': dataset_data['name'], 'passphrase': dataset_data['encryption_key']}]
                }
            )
        else:
            await middleware.call('failover.remove_encryption_keys', {'datasets': [dataset_data['name']]})
    else:
        kmip = await middleware.call('kmip.config')
        if kmip['enabled'] and kmip['manage_zfs_keys']:
            await middleware.call('failover.sync_keys_to_remote_node')


async def hook_pool_dataset_inherit_parent_encryption_root(middleware, dataset):
    await middleware.call('failover.remove_encryption_keys', {'datasets': [dataset]})


async def hook_kmip_sync(middleware, *args, **kwargs):
    await middleware.call('failover.sync_keys_to_remote_node')


async def service_remote(middleware, service, verb, options):
    """
    Most of service actions need to be replicated to the standby node so we don't lose
    too much time during failover regenerating things (e.g. users database)

    This is the middleware side of what legacy UI did on service changes.
    """
    ignore = ('system', 'nfs', 'netdata', 'truecommand', 'docker')
    if not options['ha_propagate'] or service in ignore or service == 'nginx' and verb == 'stop':
        return
    elif await middleware.call('failover.status') != 'MASTER':
        return

    try:
        await middleware.call('failover.call_remote', 'core.bulk', [
            'service.control', [[verb.upper(), service, options]]
        ], {'raise_connect_error': False})
    except Exception:
        middleware.logger.warning('Failed to run %s(%s)', verb, service, exc_info=True)


async def _event_system_ready(middleware, event_type, args):
    # called when system is ready to issue an event in case HA upgrade is pending.
    if await middleware.call('failover.status') in ('MASTER', 'SINGLE'):
        return


def remote_status_event(middleware, *args, **kwargs):
    middleware.call_sync('failover.status_refresh')


def mismatch_nics(
    local_mac_to_name: dict[str, str],
    remote_mac_to_name: dict[str, str],
    local_macs_to_remote_macs: dict[str, str],
) -> tuple[list[str], list[str]]:
    missing_local = []
    missing_remote = []

    remote_macs_to_local_macs = {v: k for k, v in local_macs_to_remote_macs.items()}

    for local_mac, local_name in local_mac_to_name.items():
        remote_mac = local_macs_to_remote_macs.get(local_mac)
        if remote_mac is None:
            missing_remote.append(f"{local_name} (has no known remote pair)")
        elif remote_mac not in remote_mac_to_name:
            missing_remote.append(f"{remote_mac} (local name {local_name})")

    for remote_mac, remote_name in remote_mac_to_name.items():
        local_mac = remote_macs_to_local_macs.get(remote_mac)
        if local_mac is None:
            missing_local.append(f"{remote_name} (has no known local pair)")
        elif local_mac not in local_mac_to_name:
            missing_local.append(f"{local_mac} (remote name {remote_name})")

    return missing_local, missing_remote


async def setup(middleware):
    middleware.event_register('failover.setup', 'Sent when failover is being setup.', roles=['FAILOVER_READ'])
    middleware.event_register('failover.status', 'Sent when failover status changes.', roles=['FAILOVER_READ'])
    middleware.event_subscribe('system.ready', _event_system_ready)
    middleware.register_hook('core.on_connect', ha_permission, sync=True)
    middleware.register_hook('interface.pre_sync', interface_pre_sync_hook, sync=True)
    middleware.register_hook('interface.post_sync', hook_setup_ha, sync=True)
    middleware.register_hook('interface.post_rollback', hook_post_rollback_setup_ha, sync=True)
    middleware.register_hook('pool.post_create_or_update', hook_setup_ha, sync=True)
    middleware.register_hook('pool.post_export', hook_pool_export, sync=True)
    middleware.register_hook('pool.post_import', hook_setup_ha, sync=True)
    middleware.register_hook('dataset.post_create', hook_pool_dataset_post_create, sync=True)
    middleware.register_hook('dataset.post_delete', hook_pool_dataset_post_delete_lock, sync=True)
    middleware.register_hook('dataset.post_lock', hook_pool_dataset_post_delete_lock, sync=True)
    middleware.register_hook('dataset.post_unlock', hook_pool_dataset_unlock, sync=True)
    middleware.register_hook('dataset.change_key', hook_pool_dataset_change_key, sync=True)
    middleware.register_hook(
        'dataset.inherit_parent_encryption_root', hook_pool_dataset_inherit_parent_encryption_root, sync=True
    )
    middleware.register_hook('kmip.sed_keys_sync', hook_kmip_sync, sync=True)
    middleware.register_hook('kmip.zfs_keys_sync', hook_kmip_sync, sync=True)
    middleware.register_hook('system.post_license_update', hook_license_update, sync=False)
    middleware.register_hook('service.pre_action', service_remote, sync=False)

    # Register callbacks to properly refresh HA status and send events on changes
    await middleware.call('failover.remote_subscribe', 'system.ready', remote_status_event)
    await middleware.call('failover.remote_subscribe', 'system.reboot', remote_status_event)
    await middleware.call('failover.remote_subscribe', 'system.shutdown', remote_status_event)
    await middleware.call('failover.remote_on_connect', remote_status_event)
    await middleware.call('failover.remote_on_disconnect', remote_status_event)

    if await middleware.call('system.ready'):
        # We add a delay here to give the standby node middleware a chance to boot up because
        # if we do it asap, it is highly likely that the standby node middleware is not ready
        # to make connection to the active node middleware.
        asyncio.get_event_loop().call_later(
            30, lambda: middleware.create_task(middleware.call('failover.sync_keys_from_remote_node'))
        )
