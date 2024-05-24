import asyncio
import base64
import errno
import json
import itertools
import logging
import os
import shutil
import socket
import stat
import textwrap
import time
from functools import partial

from middlewared.auth import is_ha_connection, TrueNasNodeSessionManagerCredentials
from middlewared.schema import accepts, Bool, Dict, Int, List, NOT_PROVIDED, Str, returns, Patch
from middlewared.service import (
    job, no_auth_required, no_authz_required, pass_app, private, CallError, ConfigService,
    ValidationError, ValidationErrors
)
import middlewared.sqlalchemy as sa
from middlewared.plugins.auth import AuthService
from middlewared.plugins.config import FREENAS_DATABASE
from middlewared.utils.contextlib import asyncnullcontext
from middlewared.plugins.failover_.zpool_cachefile import ZPOOL_CACHE_FILE, ZPOOL_CACHE_FILE_OVERWRITE
from middlewared.plugins.failover_.configure import HA_LICENSE_CACHE_KEY
from middlewared.plugins.failover_.remote import NETWORK_ERRORS
from middlewared.plugins.update_.install import STARTING_INSTALLER
from middlewared.plugins.update_.utils import DOWNLOAD_UPDATE_FILE, can_update
from middlewared.plugins.update_.utils_linux import mount_update

ENCRYPTION_CACHE_LOCK = asyncio.Lock()

logger = logging.getLogger('failover')


class FailoverModel(sa.Model):
    __tablename__ = 'system_failover'

    id = sa.Column(sa.Integer(), primary_key=True)
    disabled = sa.Column(sa.Boolean(), default=False)
    master_node = sa.Column(sa.String(1))
    timeout = sa.Column(sa.Integer(), default=0)


class FailoverService(ConfigService):

    HA_MODE = None
    LAST_STATUS = None
    LAST_DISABLEDREASONS = None

    class Config:
        datastore = 'system.failover'
        datastore_extend = 'failover.failover_extend'
        cli_private = True
        role_prefix = 'FAILOVER'

    ENTRY = Dict(
        'failover_entry',
        Int('id', required=True),
        Bool('disabled', required=True),
        Int('timeout', required=True),
        Bool('master', required=True),
    )

    @private
    async def failover_extend(self, data):
        data['master'] = await self.middleware.call('failover.node') == data.pop('master_node')
        return data

    @accepts(Patch(
        'failover_entry', 'failover_update',
        ('edit', {'name': 'master', 'method': lambda x: setattr(x, 'null', True)}),
        ('rm', {'name': 'id'}),
        ('attr', {'update': True}),
    ))
    async def do_update(self, data):
        """
        Update failover state.

        `disabled` When true indicates that HA will be disabled.
        `master`  Marks the particular node in the chassis as the master node.
                    The standby node will have the opposite value.

        `timeout` is the time to WAIT until a failover occurs when a network
            event occurs on an interface that is marked critical for failover AND
            HA is enabled and working appropriately.

            The default time to wait is 2 seconds.
            **NOTE**
                This setting does NOT effect the `disabled` or `master` parameters.
        """
        master = data.pop('master', NOT_PROVIDED)

        old = await self.middleware.call('datastore.config', 'system.failover')

        new = old.copy()
        new.update(data)

        if master is not NOT_PROVIDED:
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

    @no_authz_required
    @accepts()
    @returns(Bool())
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
        # update the class attribute so that all instances
        # of this class see the correct value
        if FailoverService.HA_MODE is None:
            FailoverService.HA_MODE = await self.middleware.call(
                'failover.enclosure.detect'
            )

        return FailoverService.HA_MODE

    @accepts(roles=['FAILOVER_READ'])
    @returns(Str())
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
        return (await self.middleware.call('failover.ha_mode'))[0]

    @accepts(roles=['FAILOVER_READ'])
    @returns(Str())
    async def node(self):
        """
        Returns the slot position in the chassis that
        the controller is located.
          A - First node
          B - Seconde Node
          MANUAL - slot position in chassis could not be determined
        """
        return (await self.middleware.call('failover.ha_mode'))[1]

    @private
    @accepts()
    @returns(List(Str('interface')))
    async def internal_interfaces(self):
        """
        This is a p2p ethernet connection on HA systems.
        """
        return await self.middleware.call('failover.internal_interface.detect')

    @no_auth_required
    @accepts()
    @returns(Str())
    @pass_app(rest=True)
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

    @accepts(roles=['FAILOVER_READ'])
    @returns(Bool())
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

    @no_auth_required
    @accepts()
    @returns(List('ips', items=[Str('ip')]))
    @pass_app(rest=True)
    async def get_ips(self, app):
        """Get a list of IPs for which the webUI can be accessed."""
        return await self.middleware.call('system.general.get_ui_urls')

    @accepts()
    @returns()
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

    @accepts(roles=['FAILOVER_WRITE'])
    @returns(Bool())
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

    @accepts(Dict(
        'options',
        Bool('reboot', default=False),
    ), roles=['FAILOVER_WRITE'])
    @returns()
    def sync_to_peer(self, options):
        """
        Sync database and files to the other controller.

        `reboot` as true will reboot the other controller after syncing.
        """
        standby = ' standby controller.'

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
        self.send_small_file('/root/.ssh/authorized_keys')
        self.send_small_file(ZPOOL_CACHE_FILE, ZPOOL_CACHE_FILE_OVERWRITE)
        self.middleware.call_sync('failover.call_remote', 'failover.zpool.cachefile.setup', ['SYNC'])

        self.middleware.call_sync(
            'failover.call_remote', 'core.call_hook', ['config.on_upload', [FREENAS_DATABASE]],
        )

        # need to make sure the license information is updated on the standby node since
        # it's cached in memory
        _prev = self.middleware.call_sync('system.product_type')
        self.middleware.call_sync(
            'failover.call_remote', 'core.call_hook', ['system.post_license_update', [_prev]]
        )

        if options['reboot']:
            self.middleware.call_sync('failover.call_remote', 'system.reboot', [{'delay': 2}])

    @accepts(roles=['FAILOVER_WRITE'])
    @returns()
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
        local_nics = await self.middleware.call('interface.get_nic_names')
        try:
            remote_nics = await self.middleware.call(
                'failover.call_remote', 'interface.get_nic_names', [],
                {'raise_connect_error': False, 'timeout': 2, 'connect_timeout': 2}
            )
        except Exception:
            self.logger.error('Unhandled exception in get_nic_names on remote controller', exc_info=True)
        else:
            result['missing_local'] = sorted(remote_nics - local_nics)
            result['missing_remote'] = sorted(local_nics - remote_nics)
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

    @accepts(Dict(
        'options',
        List(
            'pools', items=[
                Dict(
                    'pool_keys',
                    Str('name', required=True),
                    Str('passphrase', required=True)
                )
            ],
        ),
        List(
            'datasets', items=[
                Dict(
                    'dataset_keys',
                    Str('name', required=True),
                    Str('passphrase', required=True),
                )
            ],
        ),
    ))
    @returns(Bool())
    async def unlock(self, options):
        """
        Unlock datasets in HA, syncing passphrase between controllers and forcing this controller
        to be MASTER importing the pools.
        """
        if options['pools'] or options['datasets']:
            await self.middleware.call(
                'failover.update_encryption_keys', {
                    'pools': options['pools'],
                    'datasets': options['datasets'],
                },
            )

        return await self.middleware.call('failover.force_master')

    @private
    @accepts(
        Str('pool_name'),
    )
    @returns(Dict(
        List('unlocked', items=[Str('dataset')], required=True),
        Dict(
            'failed',
            required=True,
            additional_attrs=True,
            example={'vol1/enc': {'error': 'Invalid Key', 'skipped': []}},
        ),
    ))
    @job(lock=lambda args: f'failover_dataset_unlock_{args[0]}')
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
    @accepts()
    async def encryption_keys(self):
        # TODO: remove GELI key since it's
        # not supported in SCALE
        return await self.middleware.call(
            'cache.get_or_put', 'failover_encryption_keys', 0, lambda: {'geli': {}, 'zfs': {}}
        )

    @private
    @accepts(
        Dict(
            'update_encryption_keys',
            Bool('sync_keys', default=True),
            List(
                'pools', items=[
                    Dict(
                        'pool_geli_keys',
                        Str('name', required=True),
                        Str('passphrase', required=True),
                    )
                ],
            ),
            List(
                'datasets', items=[
                    Dict(
                        'dataset_keys',
                        Str('name', required=True),
                        Str('passphrase', required=True),
                    )
                ],
            ),
        )
    )
    async def update_encryption_keys(self, options):
        # TODO: remove `pools` key and `geli` logic
        # since GELI is not supported in SCALE
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
    @accepts(
        Dict(
            'remove_encryption_keys',
            Bool('sync_keys', default=True),
            List('pools', items=[Str('pool')]),
            List('datasets', items=[Str('dataset')]),
        )
    )
    async def remove_encryption_keys(self, options):
        # TODO: remove `pools` key and `geli` logic
        # since GELI is not supported in SCALE
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

    @accepts(
        Str('action', enum=['ENABLE', 'DISABLE']),
        Dict(
            'options',
            Bool('active'),
        ),
        roles=['FAILOVER_WRITE']
    )
    @returns()
    async def control(self, action, options):
        if not options:
            # The node making the call is the one we want to make MASTER by default
            node = await self._master_node((await self.middleware.call('failover.node')))
        else:
            node = await self._master_node(options.get('active'))

        failover = await self.middleware.call('datastore.config', 'system.failover')
        if action == 'ENABLE':
            if failover['disabled'] is False:
                # Already enabled
                return False
            update = {
                'disabled': False,
                'master_node': node,
            }
        elif action == 'DISABLE':
            if failover['disabled'] is True:
                # Already disabled
                return False
            update = {
                'disabled': True,
                'master_node': node,
            }

        await self.middleware.call('datastore.update', 'system.failover', failover['id'], update)

    @private
    def upgrade_version(self):
        return 1

    @accepts(Dict(
        'failover_upgrade',
        Str('train', empty=False),
        Bool('resume', default=False),
        Bool('resume_manual', default=False),
    ), roles=['FAILOVER_WRITE'])
    @returns(Bool())
    @job(lock='failover_upgrade', pipes=['input'], check_pipes=False)
    def upgrade(self, job, options):
        """
        Upgrades both controllers.

        Files will be downloaded to the Active Controller and then transferred to the Standby
        Controller.

        Upgrade process will start concurrently on both nodes.

        Once both upgrades are applied, the Standby Controller will reboot. This job will wait for
        that job to complete before finalizing.

        `resume` should be set to `true` if a previous call to this method returned a `CallError` with `errno=EAGAIN`
        meaning that an upgrade can be performed with a warning and that warning is accepted. In that case, you also
        have to set `resume_manual` to `true` if a previous call to this method was performed using update file upload.
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

        train = options.get('train')
        if train:
            self.middleware.call_sync('update.set_train', train)

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

                djob = self.middleware.call_sync('update.download', job_on_progress_cb=download_callback)
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

            existing_bootenvs = set([
                be['name'] for be in self.middleware.call_sync('bootenv.query')
            ] + [
                be['name'] for be in self.middleware.call_sync('failover.call_remote', 'bootenv.query')
            ])
            if bootenv_name in existing_bootenvs:
                for i in itertools.count(1):
                    probe_bootenv_name = f"{bootenv_name}-{i}"
                    if probe_bootenv_name not in existing_bootenvs:
                        bootenv_name = probe_bootenv_name
                        break

            dataset_name = f'{self.middleware.call_sync("boot.pool_name")}/ROOT/{bootenv_name}'

            self.middleware.call_sync('keyvalue.set', 'HA_UPGRADE', True)

            remote_path = self.middleware.call_sync('failover.call_remote', 'update.get_update_location')

            if not options['resume']:
                # Replicate uploaded or downloaded update it to the standby
                job.set_progress(None, 'Sending files to Standby Controller')
                token = self.middleware.call_sync('failover.call_remote', 'auth.generate_token')
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
                'failover.call_remote', 'system.reboot',
                [{'delay': 5}],
                {'job': True}
            )
        except Exception:
            raise

        # The upgrade procedure will upgrade both systems simultaneously
        # as well as activate the new BEs. The standby controller will be
        # automatically rebooted into the new BE to "finalize" the upgrade.
        # However, we will re-activate the old BE on the active controller
        # to give the end-user a chance to "test" the new upgrade so in the
        # rare case something horrendous occurs on the new version they can
        # simply "reboot" (to cause a failover) and faill back to the
        # controller running the old version of the software.
        # The procedure is supposed to look like this:
        #   1. upgrade both controllers
        #   2. standby controller activates new BE and reboots
        #   3. end-user verifies the standby controller upgraded without issues
        #   4. end-user then failovers (reboots) to the newly upgraded node
        #   5. end-user verifies that the new software functions as expected
        #   6. end-user is then presented with a webUI option to "apply pending upgrade"
        #   7. end-user chooses that webUI option
        #   8. after webUI option is chosen, standby node is rebooted to "finalize" the
        #       upgrade procedure
        local_bootenv = self.middleware.call_sync('bootenv.query', [('active', 'rin', 'N')])
        if not local_bootenv:
            raise CallError('Could not find current boot environment.')
        self.middleware.call_sync('bootenv.activate', local_bootenv[0]['id'])

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

        return True

    @private
    def upgrade_waitstandby(self, seconds=1200):
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

            except CallError as e:
                if e.errno in NETWORK_ERRORS:
                    time.sleep(5)
                    continue
                raise
            else:
                return True
        return False

    @accepts(roles=['FAILOVER_READ'])
    @returns(Bool())
    def upgrade_pending(self):
        """
        Verify if HA upgrade is pending.

        `upgrade_finish` needs to be called to finish
        the HA upgrade process if this method returns true.
        """

        if self.middleware.call_sync('failover.status') != 'MASTER':
            raise CallError('Upgrade can only be run from the Active Controller.')

        if self.middleware.call_sync('keyvalue.get', 'HA_UPGRADE', False) is not True:
            return False

        if self.middleware.call_sync('core.get_jobs', [['method', '=', 'failover.upgrade'], ['state', '=', 'RUNNING']]):
            # We don't want to prematurely set `HA_UPGRADE` to false in the event that remote is still updating
            # and reports the same version as active - so we would want to make sure that no HA upgrade job
            # is executing at the moment.
            return False

        try:
            assert self.middleware.call_sync('failover.call_remote', 'core.ping') == 'pong'
        except Exception:
            return False

        local_version = self.middleware.call_sync('system.version')
        remote_version = self.middleware.call_sync('failover.call_remote', 'system.version')

        if local_version == remote_version:
            self.middleware.call_sync('keyvalue.set', 'HA_UPGRADE', False)
            return False

        if not self.middleware.call_sync('failover.call_remote', 'bootenv.query', [[('active', '=', 'NR')]]):
            raise CallError('Remote controller must reboot to activate pending boot environment')

        return can_update(remote_version, local_version)

    @accepts(roles=['FAILOVER_WRITE'])
    @returns(Bool())
    @job(lock='failover_upgrade_finish')
    def upgrade_finish(self, job):
        """
        Perform the last stage of an HA upgrade.

        This will activate the new boot environment on the
        Standby Controller and reboot it.
        """

        if self.middleware.call_sync('failover.status') != 'MASTER':
            raise CallError('Upgrade can only run on Active Controller.')

        job.set_progress(None, 'Ensuring the Standby Controller is booted')
        if not self.upgrade_waitstandby():
            raise CallError('Timed out waiting for the Standby Controller to boot.')

        job.set_progress(None, 'Activating new boot environment')
        local_bootenv = self.middleware.call_sync('bootenv.query', [('active', 'rin', 'N')])
        if not local_bootenv:
            raise CallError('Could not find current boot environment.')
        self.middleware.call_sync('failover.call_remote', 'bootenv.activate', [local_bootenv[0]['id']])

        job.set_progress(None, 'Rebooting Standby Controller')
        self.middleware.call_sync('failover.call_remote', 'system.reboot', [{'delay': 10}])
        self.middleware.call_sync('keyvalue.set', 'HA_UPGRADE', False)
        return True

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
    # Skip if session was already authenticated
    if app is not None and app.authenticated is True:
        return

    # We only care for remote connections (IPv4), in the interlink
    try:
        sock = app.request.transport.get_extra_info('socket')
    except AttributeError:
        # app.request or app.request.transport can be None
        return

    if sock.family != socket.AF_INET:
        return

    remote_addr, remote_port = app.request.transport.get_extra_info('peername')
    if is_ha_connection(remote_addr, remote_port):
        await AuthService.session_manager.login(app, TrueNasNodeSessionManagerCredentials())


async def interface_pre_sync_hook(middleware):
    await middleware.call('failover.internal_interface.pre_sync')


async def hook_license_update(middleware, *args, **kwargs):
    FailoverService.HA_MODE = None
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
        await middleware.call('failover.call_remote', 'service.start', ['ssh'])

    middleware.logger.debug('[HA] Refreshing failover status')
    await middleware.call('failover.status_refresh')

    middleware.logger.info('[HA] Setup complete')

    middleware.send_event('failover.setup', 'ADDED', fields={})


async def hook_pool_export(middleware, pool=None, *args, **kwargs):
    await middleware.call('enclosure.sync_zpool', pool)
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
    ignore = ('system', 'smartd', 'nfs', 'netdata', 'truecommand', 'idmap', 'sssd', 'cifs')
    if not options['ha_propagate'] or service in ignore or service == 'nginx' and verb == 'stop':
        return
    elif await middleware.call('failover.status') != 'MASTER':
        return

    try:
        await middleware.call('failover.call_remote', 'core.bulk', [
            f'service.{verb}', [[service, options]]
        ], {'raise_connect_error': False})
    except Exception:
        middleware.logger.warning('Failed to run %s(%s)', verb, service, exc_info=True)


async def _event_system_ready(middleware, event_type, args):
    # called when system is ready to issue an event in case HA upgrade is pending.
    if await middleware.call('failover.status') in ('MASTER', 'SINGLE'):
        return

    if await middleware.call('keyvalue.get', 'HA_UPGRADE', False):
        middleware.send_event('failover.upgrade_pending', 'ADDED', id='BACKUP', fields={'pending': True})


def remote_status_event(middleware, *args, **kwargs):
    middleware.call_sync('failover.status_refresh')


async def setup(middleware):
    middleware.event_register('failover.setup', 'Sent when failover is being setup.')
    middleware.event_register('failover.status', 'Sent when failover status changes.', no_auth_required=True)
    middleware.event_register('failover.upgrade_pending', textwrap.dedent('''\
        Sent when system is ready and HA upgrade is pending.

        It is expected the client will react by issuing `upgrade_finish` call
        at user will.'''))
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
