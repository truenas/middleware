# Copyright (c) 2019 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

import asyncio
import base64
import errno
import json
from lockfile import LockFile
import netif
import os
import requests
import shutil
import socket
import subprocess
import sys
import sysctl
import textwrap
import time

from collections import defaultdict
from functools import partial

from middlewared.client import Client, ClientException, CallTimeout
from middlewared.schema import accepts, Bool, Dict, Int, List, Str
from middlewared.service import (
    job, no_auth_required, pass_app, private, throttle, CallError, ConfigService, ValidationErrors,
)
from middlewared.plugins.auth import AuthService, SessionManagerCredentials
from middlewared.utils import run

# FIXME: temporary imports while license methods are still in django
if '/usr/local/www' not in sys.path:
    sys.path.append('/usr/local/www')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'freenasUI.settings')
import django
django.setup()
from freenasUI.freeadmin.sqlite3_ha.base import Journal
from freenasUI.failover.detect import ha_hardware, ha_node
from freenasUI.failover.enc_helper import LocalEscrowCtl
from freenasUI.middleware.notifier import notifier

INTERNAL_IFACE_NF = '/tmp/.failover_internal_iface_not_found'
SYNC_FILE = '/var/tmp/sync_failed'


class TruenasNodeSessionManagerCredentials(SessionManagerCredentials):
    pass


def throttle_condition(middleware, app, *args, **kwargs):
    # app is None means internal middleware call
    if app is None or (app and app.authenticated):
        return True, 'AUTHENTICATED'
    return False, None


class RemoteClient(object):

    def __init__(self, remote_ip):
        self.remote_ip = remote_ip

    def __enter__(self):
        # 860 is the iSCSI port and blocked by the failover script
        try:
            self.client = Client(
                f'ws://{self.remote_ip}:6000/websocket',
                reserved_ports=True, reserved_ports_blacklist=[860],
            )
        except ConnectionRefusedError:
            raise CallError('Connection refused', errno.ECONNREFUSED)
        except OSError as e:
            if e.errno in (
                errno.ENETDOWN, errno.EHOSTDOWN, errno.ENETUNREACH, errno.EHOSTUNREACH
            ) or isinstance(e, socket.timeout):
                raise CallError('Standby node is down', errno.EHOSTDOWN)
            raise
        return self

    def call(self, *args, **kwargs):
        try:
            return self.client.call(*args, **kwargs)
        except ClientException as e:
            raise CallError(str(e), e.errno)

    def __exit__(self, typ, value, traceback):
        self.client.close()
        if typ is None:
            return
        if typ is ClientException:
            raise CallError(str(value), value.errno)

    def sendfile(self, token, local_path, remote_path):
        r = requests.post(
            f'http://{self.remote_ip}:6000/_upload/',
            files=[
                ('data', json.dumps({
                    'method': 'filesystem.put',
                    'params': [remote_path],
                })),
                ('file', open(local_path, 'rb')),
            ],
            headers={
                'Authorization': f'Token {token}',
            },
        )
        job_id = r.json()['job_id']
        # TODO: use event subscription in the client instead of polling
        while True:
            rjob = self.client.call('core.get_jobs', [('id', '=', job_id)])
            if rjob:
                rjob = rjob[0]
                if rjob['state'] == 'FAILED':
                    raise CallError(
                        f'Failed to send {local_path} to Standby Controller: {job["error"]}.'
                    )
                elif rjob['state'] == 'ABORTED':
                    raise CallError(
                        f'Failed to send {local_path} to Standby Controller, job aborted by user.'
                    )
                elif rjob['state'] == 'SUCCESS':
                    break
            time.sleep(0.5)


class FailoverService(ConfigService):

    class Config:
        datastore = 'failover.failover'

    @accepts(Dict(
        'failover_update',
        Bool('disabled'),
        Int('timeout'),
        Bool('master'),
    ))
    async def do_update(self, data):
        """
        Update failover state.

        `disabled` as false will turn off HA.
        `master` sets the state of current node. Standby node will have the opposite value.
        """
        old = await self.config()

        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()
        if new['disabled'] is False:
            if not await self.middleware.call('interface.query', [('failover_critical', '=', True)]):
                verrors.add(
                    'failover_update.disabled',
                    'You need at least one critical interface to disable failover.',
                )
        verrors.check()

        await self.middleware.call('datastore.update', 'failover.failover', new['id'], new)

        if await self.middleware.call('pool.query', [('status', '!=', 'OFFLINE')]):
            cp = await run('fenced', '--force', check=False)
            # 6 = Already running
            if cp.returncode not in (0, 6):
                raise CallError(f'fenced failed with exit code {cp.returncode}.')

        try:
            await self.middleware.call('failover.call_remote', 'datastore.sql', [
                "UPDATE system_failover SET master = %s", [str(int(not new['disabled']))]
            ])
        except Exception:
            self.logger.warn('Failed to set master flag on standby node', exc_info=True)

        await self.middleware.call('service.start', 'ix-devd')

        return await self.config()

    @accepts()
    def licensed(self):
        """
        Checks whether this instance is licensed as a HA unit.
        """
        info = self.middleware.call_sync('system.info')
        if not info['license'] or not info['license']['system_serial_ha']:
            return False
        return True

    @accepts()
    def hardware(self):
        """
        Gets the hardware type of HA.

          ECHOSTREAM
          ECHOWARP
          PUMA
          SBB
          ULTIMATE
          MANUAL
        """
        return ha_hardware()

    @accepts()
    def node(self):
        """
        Gets the node identification.
          A - First node
          B - Seconde Node
          MANUAL - could not be identified, its in manual mode
        """
        node = ha_node()
        if node is None:
            return 'MANUAL'
        return node

    @private
    @accepts()
    def internal_interfaces(self):
        """
        Interfaces used internally for HA.
        It is a direct link between the nodes.
        """
        hardware = self.hardware()
        if hardware == 'ECHOSTREAM':
            stdout = subprocess.check_output('/usr/sbin/pciconf -lv | grep "card=0xa01f8086 chip=0x10d38086"',
                                             shell=True, encoding='utf8')
            if not stdout:
                if not os.path.exists(INTERNAL_IFACE_NF):
                    open(INTERNAL_IFACE_NF, 'w').close()
                return []
            return [stdout.split('@')[0]]
        elif hardware == 'SBB':
            return ['ix0']
        elif hardware in ('ECHOWARP', 'PUMA'):
            return ['ntb0']
        elif hardware == 'ULTIMATE':
            return ['igb1']
        elif hardware == 'BHYVE':
            return ['em0']
        return []

    @private
    async def get_carp_states(self, interfaces=None):
        if interfaces is None:
            interfaces = await self.middleware.call('interface.query')
        masters, backups, inits = [], [], []
        internal_interfaces = await self.middleware.call('failover.internal_interfaces')
        for iface in interfaces:
            if iface['name'] in internal_interfaces:
                continue
            if not iface['state']['carp_config']:
                continue
            if iface['state']['carp_config'][0]['state'] == 'MASTER':
                masters.append(iface['name'])
            elif iface['state']['carp_config'][0]['state'] == 'BACKUP':
                backups.append(iface['name'])
            elif iface['state']['carp_config'][0]['state'] == 'INIT':
                inits.append(iface['name'])
            else:
                self.logger.warning('Unknown CARP state %r for interface %s', iface['state']['carp_config'][0]['state'],
                                    iface['name'])
        return masters, backups, inits

    @private
    async def check_carp_states(self, local, remote):
        errors = []
        interfaces = set(local[0] + local[1] + remote[0] + remote[1])
        if not interfaces:
            errors.append(f"There are no failover interfaces")
        for name in interfaces:
            if name not in local[0] + local[1]:
                errors.append(f"Interface {name} is not configured for failover on local system")
            if name not in remote[0] + remote[1]:
                errors.append(f"Interface {name} is not configured for failover on remote system")
            if name in local[0] and name in remote[0]:
                errors.append(f"Interface {name} is MASTER on both nodes")
            if name in local[1] and name in remote[1]:
                errors.append(f"Interface {name} is BACKUP on both nodes")
        for name in set(local[2] + remote[2]):
            if name not in local[2]:
                errors.append(f"Interface {name} is in a non-functioning state on local system")
            if name not in remote[2]:
                errors.append(f"Interface {name} is in a non-functioning state on remote system")

        return errors

    @no_auth_required
    @throttle(seconds=2, condition=throttle_condition)
    @accepts()
    @pass_app
    async def status(self, app):
        """
        Return the current status of this node in the failover

        Returns:
            MASTER
            BACKUP
            ELECTING
            IMPORTING
            ERROR
            SINGLE
        """
        interfaces = await self.middleware.call('interface.query')
        if not any(filter(lambda x: x.get('failover_virtual_aliases'), interfaces)):
            return 'SINGLE'

        pools = await self.middleware.call('pool.query')
        if not pools:
            return 'SINGLE'

        if not await self.middleware.call('failover.licensed'):
            return 'SINGLE'

        masters = (await self.get_carp_states(interfaces))[0]
        if masters:
            if any(filter(lambda x: x.get('status') != 'OFFLINE', pools)):
                return 'MASTER'
            if os.path.exists('/tmp/.failover_electing'):
                return 'ELECTING'
            elif os.path.exists('/tmp/.failover_importing'):
                return 'IMPORTING'
            elif os.path.exists('/tmp/.failover_failed'):
                return 'ERROR'

        try:
            remote_imported = await self.middleware.call('failover.call_remote', 'pool.query', [
                [['status', '!=', 'OFFLINE']]
            ])
            # Other node has the pool
            if remote_imported or not pools:
                # check for carp MASTER (any) in remote?
                return 'BACKUP'
            # Other node has no pool
            elif not remote_imported:
                # check for carp MASTER (none) in remote?
                return 'ERROR'
            # We couldn't contact the other node
            else:
                return 'UNKNOWN'
        except Exception as e:
            # Anything other than ClientException is unexpected and should be logged
            if not isinstance(e, CallError):
                self.logger.warn('Failed checking failover status', exc_info=True)
            return 'UNKNOWN'

    @accepts()
    def in_progress(self):
        """
        Returns true if current node is still initializing after failover event
        """
        FAILOVER_EVENT = '/tmp/.failover_event'
        return LockFile(FAILOVER_EVENT).is_locked()

    @no_auth_required
    @throttle(seconds=2, condition=throttle_condition)
    @accepts()
    @pass_app
    async def get_ips(self, app):
        """
        Get a list of IPs which can be accessed for management via UI.
        """
        addresses = (await self.middleware.call('system.general.config'))['ui_address']
        if '0.0.0.0' in addresses:
            ips = []
            for interface in await self.middleware.call('interface.query', [
                ('failover_vhid', '!=', None)
            ]):
                ips += [i['address'] for i in interface.get('failover_virtual_aliases', [])]
            return ips
        return addresses

    @accepts()
    def force_master(self):
        """
        Force this controller to become MASTER.
        """
        cp = subprocess.run(['fenced', '--force'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if cp.returncode not in (0, 6):
            return False
        for i in self.middleware.call_sync('interface.query', [('failover_critical', '!=', None)]):
            if i['failover_vhid']:
                subprocess.run([
                    'python',
                    '/usr/local/libexec/truenas/carp-state-change-hook.py',
                    f'{i["failover_vhid"]}@{i["name"]}',
                    'forcetakeover',
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
                break
        return False

    @accepts(Dict(
        'options',
        Bool('reboot', default=False),
    ))
    def sync_to_peer(self, options):
        """
        Sync database and files to the other controller.

        `reboot` as true will reboot the other controller after syncing.
        """
        self.logger.debug('Syncing database to standby controller')
        self.database_sync()
        self.logger.debug('Sending license and pwenc files')
        self.send_small_file('/data/license')
        self.send_small_file('/data/pwenc_secret')
        self.send_small_file('/root/.ssh/authorized_keys')

        for path in ('/data/geli', '/data/ssh'):
            if not os.path.exists(path) or not os.path.isdir(path):
                continue
            for f in os.listdir(path):
                fullpath = os.path.join(path, f)
                if not os.path.isfile(fullpath):
                    continue
                self.send_small_file(fullpath)

        self.middleware.call_sync('failover.call_remote', 'service.start', ['ix-devd'])

        if options['reboot']:
            self.middleware.call_sync('failover.call_remote', 'system.reboot', [{'delay': 2}])

    @accepts()
    def sync_from_peer(self):
        """
        Sync database and files from the other controller.
        """
        self.middleware.call_sync('failover.call_remote', 'failover.sync_to_peer')

    @private
    def send_small_file(self, path, dest=None):
        if dest is None:
            dest = path
        if not os.path.exists(path):
            return
        mode = os.stat(path).st_mode
        with open(path, 'rb') as f:
            first = True
            while True:
                read = f.read(1024 * 1024 * 10)
                if not read:
                    break
                self.middleware.call_sync('failover.call_remote', 'filesystem.file_receive', [
                    dest, base64.b64encode(read).decode(), {'mode': mode, 'append': not first}
                ])
                first = False

    @no_auth_required
    @throttle(seconds=2, condition=throttle_condition)
    @accepts()
    @pass_app
    def disabled_reasons(self, app):
        """
        Returns a list of reasons why failover is not enabled/functional.

        NO_VOLUME - There are no pools configured.
        NO_VIP - There are no interfaces configured with Virtual IP.
        NO_SYSTEM_READY - Other storage controller has not finished booting.
        NO_PONG - Other storage controller is not communicable.
        NO_FAILOVER - Failover is administratively disabled.
        NO_LICENSE - Other storage controller has no license.
        DISAGREE_CARP - Nodes CARP states do not agree.
        MISMATCH_DISKS - The storage controllers do not have the same quantity of disks.
        NO_CRITICAL_INTERFACES - No network interfaces are marked critical for failover.
        """
        reasons = []
        if not self.middleware.call_sync('pool.query'):
            reasons.append('NO_VOLUME')
        if not any(filter(
            lambda x: x.get('failover_virtual_aliases'), self.middleware.call_sync('interface.query'))
        ):
            reasons.append('NO_VIP')
        try:
            assert self.middleware.call_sync('failover.call_remote', 'core.ping') == 'pong'
            # This only matters if it has responded to 'ping', otherwise
            # there is no reason to even try
            if not self.middleware.call_sync('failover.call_remote', 'system.ready'):
                reasons.append('NO_SYSTEM_READY')

            if not self.middleware.call_sync('failover.call_remote', 'failover.licensed'):
                reasons.append('NO_LICENSE')

            local = self.middleware.call_sync('failover.get_carp_states')
            remote = self.middleware.call_sync('failover.call_remote', 'failover.get_carp_states')
            if self.middleware.call_sync('failover.check_carp_states', local, remote):
                reasons.append('DISAGREE_CARP')

            mismatch_disks = self.middleware.call_sync('failover.mismatch_disks')
            if mismatch_disks['missing_local'] or mismatch_disks['missing_remote']:
                reasons.append('MISMATCH_DISKS')

            if not self.middleware.call_sync('datastore.query', 'network.interfaces', [['int_critical', '=', True]]):
                reasons.append('NO_CRITICAL_INTERFACES')
        except CallError as e:
            if e.errno not in (errno.ECONNREFUSED, errno.EHOSTDOWN, ClientException.ENOMETHOD):
                reasons.append('NO_PONG')
            else:
                try:
                    assert self.middleware.call_sync('failover.legacy_ping') == 'pong'
                except Exception:
                    reasons.append('NO_PONG')
        except Exception:
            reasons.append('NO_PONG')
        if self.middleware.call_sync('failover.config')['disabled']:
            reasons.append('NO_FAILOVER')
        return reasons

    @private
    async def mismatch_disks(self):
        local_disks = set(filter(
            lambda x: x.startswith('da'),
            (await self.middleware.call('device.get_info', 'DISK')).keys(),
        ))
        remote_disks = set(filter(
            lambda x: x.startswith('da'),
            (await self.middleware.call('failover.call_remote', 'device.get_info', ['DISK'])).keys(),
        ))
        return {
            'missing_local': sorted(remote_disks - local_disks),
            'missing_remote': sorted(local_disks - remote_disks),
        }

    @accepts(Dict(
        'options',
        Str('passphrase', password=True, required=True),
    ))
    def unlock(self, options):
        """
        Unlock pools in HA, syncing passphrase between controllers and forcing this controller
        to be MASTER importing the pools.
        """
        self.middleware.call('failover.encryption_setkey', options['passphrase'])
        return self.middleware.call('failover.force_master')

    @private
    def legacy_ping(self):
        # This is to communicate with legacy TrueNAS, pre middlewared for upgrading.
        return notifier().failover_rpc().ping()

    @private
    def remote_ip(self):
        node = self.node()
        if node == 'A':
            remote = '169.254.10.2'
        elif node == 'B':
            remote = '169.254.10.1'
        else:
            raise CallError(f'Node {node} invalid for call_remote', errno.EBADRPC)
        return remote

    @accepts(
        Str('method'),
        List('args', default=[]),
        Dict(
            'options',
            Int('timeout'),
            Bool('job', default=False),
        ),
    )
    def call_remote(self, method, args, options=None):
        options = options or {}
        remote = self.remote_ip()
        with RemoteClient(remote) as c:
            try:
                return c.call(method, *args, **options)
            except CallTimeout:
                raise CallError('Call timeout', errno.ETIMEDOUT)

    @private
    @accepts()
    def encryption_getkey(self):
        # FIXME: we could get rid of escrow, middlewared can do that job
        escrowctl = LocalEscrowCtl()
        return escrowctl.getkey()

    @private
    @accepts(Str('passphrase'), Dict('options', Bool('sync', default=True)))
    def encryption_setkey(self, passphrase, options=None):
        # FIXME: we could get rid of escrow, middlewared can do that job
        escrowctl = LocalEscrowCtl()
        rv = escrowctl.setkey(passphrase)
        if not rv:
            return rv
        if options['sync']:
            try:
                self.call_remote('failover.encryption_setkey', [passphrase, {'sync': False}])
            except Exception as e:
                self.logger.warn('Failed to set encryption key on standby node: %s', e)
        return rv

    @private
    @accepts()
    def encryption_clearkey(self):
        # FIXME: we could get rid of escrow, middlewared can do that job
        escrowctl = LocalEscrowCtl()
        return escrowctl.clear()

    @accepts(
        Str('action', enum=['ENABLE', 'DISABLE']),
        Dict(
            'options',
            Bool('active'),
        ),
    )
    async def control(self, action, options=None):
        if options is None:
            options = {}

        failover = await self.middleware.call('datastore.config', 'failover.failover')
        if action == 'ENABLE':
            if failover['disabled'] is False:
                # Already enabled
                return False
            failover.update({
                'disabled': False,
                'master': False,
            })
            await self.middleware.call('datastore.update', 'failover.failover', failover['id'], failover)
            await self.middleware.call('service.start', 'ix-devd')
        elif action == 'DISABLE':
            if failover['disabled'] is True:
                # Already disabled
                return False
            failover['master'] = True if options.get('active') else False
            await self.middleware.call('datastore.update', 'failover.failover', failover['id'], failover)
            await self.middleware.call('service.start', 'ix-devd')

    @private
    @accepts()
    def database_sync(self):
        dump = self.middleware.call_sync('datastore.dump')
        with Journal() as j:
            restore = self.call_remote('datastore.restore', [dump])
            if restore:
                j.queries = []
        return restore

    @private
    def upgrade_version(self):
        return 1

    @accepts(Dict(
        'failover_upgrade',
        Str('train', empty=False),
    ))
    @job(lock='failover_upgrade', pipes=['input'], check_pipes=False)
    def upgrade(self, job, options):
        """
        Upgrades both controllers.

        Files will be downloaded in the Active Controller and then transferred to the Standby
        Controller.

        Upgrade process will start concurrently on both nodes.

        Once both upgrades are applied the Standby Controller will reboot and this job will wait for it
        to complete the boot process, finalizing this job.
        """

        if self.middleware.call_sync('failover.status') != 'MASTER':
            raise CallError('Upgrade can only run on Active Controller.')

        try:
            job.check_pipe('input')
        except ValueError:
            updatefile = False
        else:
            updatefile = True

        train = options.get('train')
        if train:
            self.middleware.call_sync('update.set_train', train)

        local_path = self.middleware.call_sync('update.get_update_location')

        if updatefile:
            updatefile_name = 'updatefile.tar'
            job.set_progress(None, 'Uploading update file')
            updatefile_localpath = os.path.join(local_path, updatefile_name)
            os.makedirs(local_path, exist_ok=True)
            with open(updatefile_localpath, 'wb') as f:
                shutil.copyfileobj(job.pipes.input.r, f, 1048576)
        else:
            def download_callback(j):
                job.set_progress(None, j['progress']['description'] or 'Downloading upgrade files')

            # Download update first so we can transfer it to the other node.
            djob = self.middleware.call_sync('update.download', job_on_progress_cb=download_callback)
            djob.wait_sync()
            if djob.error:
                raise CallError(f'Error downloading update: {djob.error}')
            if not djob.result:
                raise CallError('No updates available.')

        remote_ip = self.remote_ip()
        with RemoteClient(remote_ip) as remote:

            if not remote.call('system.ready'):
                raise CallError('Standby Controller is not ready, wait boot process.')

            legacy_upgrade = False
            try:
                remote.call('failover.upgrade_version')
            except CallError as e:
                if e.errno == CallError.ENOMETHOD:
                    legacy_upgrade = True
                else:
                    raise

            self.middleware.call_sync('keyvalue.set', 'HA_UPGRADE', True)

            job.set_progress(None, 'Sending files to Standby Controller')
            remote.call('update.destroy_upload_location')
            remote_path = remote.call('update.create_upload_location')
            token = remote.call('auth.generate_token')

            for f in os.listdir(local_path):
                remote.sendfile(token, os.path.join(local_path, f), os.path.join(remote_path, f))

            local_version = self.middleware.call_sync('system.version')
            remote_version = remote.call('system.version')

            update_remote_descr = update_local_descr = 'Starting upgrade'

            def callback(j, controller):
                nonlocal update_local_descr, update_remote_descr
                if j['state'] != 'RUNNING':
                    return
                if controller == 'LOCAL':
                    update_local_descr = f'{j["progress"]["percent"]}%: {j["progress"]["description"]}'
                else:
                    update_remote_descr = f'{j["progress"]["percent"]}%: {j["progress"]["description"]}'
                job.set_progress(
                    None, (
                        f'Active Controller: {update_local_descr}\n' if not legacy_upgrade else ''
                    ) + f'Standby Controller: {update_remote_descr}'
                )

            if updatefile:
                update_method = 'update.manual'
                update_remote_args = [os.path.join(remote_path, updatefile_name)]
                update_local_args = [updatefile_localpath]
            else:
                update_method = 'update.update'
                update_remote_args = []
                update_local_args = []

            # If they are the same we assume this is a clean upgade so we start by
            # upgrading the standby controller.
            if legacy_upgrade or local_version == remote_version:
                rjob = remote.call(update_method, *update_remote_args, job='RETURN', callback=partial(
                    callback, controller='REMOTE',
                ))
            else:
                rjob = None

            if not legacy_upgrade:
                ljob = self.middleware.call_sync(update_method, *update_local_args, job_on_progress_cb=partial(
                    callback, controller='LOCAL',
                ))
                ljob.wait_sync()
                if ljob.error:
                    raise CallError(ljob.error)

                remote_boot_id = remote.call('system.boot_id')

            if rjob:
                rjob.result()

            remote.call('system.reboot', {'delay': 5}, job=True)

        if not legacy_upgrade:
            # Update will activate the new boot environment.
            # We want to reactivate the current boot environment so on reboot for failover
            # the user has a chance to verify the new version is working as expected before
            # move on and have both controllers on new version.
            local_bootenv = self.middleware.call_sync('bootenv.query', [('active', 'rin', 'N')])
            if not local_bootenv:
                raise CallError('Could not find current boot environment.')
            self.middleware.call_sync('bootenv.activate', local_bootenv[0]['id'])

        job.set_progress(None, 'Waiting Standby Controller to reboot.')

        # Wait enough that standby controller has stopped receiving new connections and is
        # rebooting.
        try:
            with RemoteClient(remote_ip) as remote:
                retry_time = time.monotonic()
                shutdown_timeout = sysctl.filter('kern.init_shutdown_timeout')[0].value
                while time.monotonic() - retry_time < shutdown_timeout:
                    remote.call('core.ping')
                    time.sleep(5)
        except CallError:
            pass
        else:
            raise CallError('Standby Controller failed to reboot.', errno.ETIMEDOUT)

        if not self.upgrade_waitstandby(remote_ip=remote_ip):
            raise CallError('Timed out waiting Standby Controller after upgrade.')

        if not legacy_upgrade and remote_boot_id == self.call_remote('system.boot_id'):
            raise CallError('Standby Controller failed to reboot.')

        return True

    @private
    def upgrade_waitstandby(self, remote_ip=None, seconds=900):
        """
        We will wait up to 15 minutes by default for the Standby Controller to reboot.
        This values come from observation from support of how long a M-series can take.
        """
        if remote_ip is None:
            remote_ip = self.remote_ip()
        retry_time = time.monotonic()
        while time.monotonic() - retry_time < seconds:
            try:
                with RemoteClient(remote_ip) as c:
                    if not c.call('system.ready'):
                        time.sleep(5)
                        continue
                    return True
            except CallError as e:
                if e.errno in (errno.ECONNREFUSED, errno.EHOSTDOWN):
                    time.sleep(5)
                    continue
                raise
        return False

    @accepts()
    def upgrade_pending(self):
        """
        Verify if HA upgrade is pending.

        `upgrade_finish` needs to be called to finish HA upgrade if this method returns true.
        """

        if self.middleware.call_sync('failover.status') != 'MASTER':
            raise CallError('Upgrade can only run on Active Controller.')

        if not self.middleware.call_sync('keyvalue.get', 'HA_UPGRADE', False):
            return False
        try:
            assert self.call_remote('system.ping') == 'pong'
        except Exception:
            return True
        local_version = self.middleware.call_sync('system.version')
        remote_version = self.call_remote('system.version')
        if local_version == remote_version:
            self.middleware.call_sync('keyvalue.set', 'HA_UPGRADE', False)
            return False

        local_bootenv = self.middleware.call_sync('bootenv.query', [('active', 'rin', 'N')])
        if local_bootenv:
            remote_bootenv = self.call_remote('bootenv.query', [[
                ('active', 'rin', 'R'),
                ('id', '=', local_bootenv[0]['id']),
            ]])
            if remote_bootenv:
                return True
        return False

    @accepts()
    @job(lock='failover_upgrade_finish')
    def upgrade_finish(self, job):
        """
        Perform last stage of HA upgrade.

        This will activate the new boot environment in Standby Controller and reboot it.
        """

        if self.middleware.call_sync('failover.status') != 'MASTER':
            raise CallError('Upgrade can only run on Active Controller.')

        job.set_progress(None, 'Waiting for Standby Controller to boot')
        if not self.upgrade_waitstandby():
            raise CallError('Timed out waiting Standby Controller to boot.')

        job.set_progress(None, 'Activating new boot environment')
        local_bootenv = self.middleware.call_sync('bootenv.query', [('active', 'rin', 'N')])
        if not local_bootenv:
            raise CallError('Could not find current boot environment.')
        self.call_remote('bootenv.activate', [local_bootenv[0]['id']])

        job.set_progress(None, 'Rebooting Standby Controller')
        self.call_remote('system.reboot', [{'delay': 10}])
        self.middleware.call_sync('keyvalue.set', 'HA_UPGRADE', False)
        return True


async def ha_permission(middleware, app):
    # Skip if session was already authenticated
    if app.authenticated is True:
        return

    # We only care for remote connections (IPv4), in the interlink
    sock = app.request.transport.get_extra_info('socket')
    if sock.family != socket.AF_INET:
        return

    remote_addr, remote_port = app.request.transport.get_extra_info('peername')

    if remote_port <= 1024 and remote_addr in (
        '169.254.10.1',
        '169.254.10.2',
        '169.254.10.20',
        '169.254.10.80',
    ):
        AuthService.session_manager.login(app, TruenasNodeSessionManagerCredentials())


async def hook_geli_passphrase(middleware, pool, passphrase):
    """
    Hook to set pool passphrase when its changed.
    """
    if not passphrase:
        return
    if not await middleware.call('failover.licensed'):
        return
    await middleware.call('failover.encryption_setkey', passphrase, {'sync': True})


def journal_sync(middleware, retries):
    with Journal() as j:
        for q in list(j.queries):
            query, params = q
            try:
                middleware.call_sync('failover.call_remote', 'datastore.sql', [query, params])
            except Exception as e:
                if isinstance(e, CallError) and e.errno in [errno.ECONNREFUSED, errno.EHOSTDOWN]:
                    middleware.logger.trace('Skipping journal sync, node down')
                    break

                retries[str(q)] += 1
                if retries[str(q)] >= 2:
                    # No need to warn/log multiple times the same thing
                    continue

                middleware.logger.exception('Failed to run query %s: %r', query, e)

                try:
                    if not os.path.exists(SYNC_FILE):
                        open(SYNC_FILE, 'w').close()
                except Exception:
                    pass

                break
            else:
                j.queries.remove(q)

        if len(list(j.queries)) == 0 and os.path.exists(SYNC_FILE):
            try:
                os.unlink(SYNC_FILE)
            except Exception:
                pass


async def journal_ha(middleware):
    """
    This is a green thread reponsible for trying to sync the journal
    file to the other node.
    Every SQL query that could not be synced is stored in the journal.
    """
    retries = defaultdict(int)
    while True:
        await asyncio.sleep(5)
        if Journal.is_empty():
            continue
        try:
            await middleware.run_in_thread(journal_sync, middleware, retries)
        except Exception:
            middleware.logger.warn('Failed to sync journal', exc_info=True)


def sync_internal_ips(middleware, iface, carp1_skew, carp2_skew, internal_ip):
    try:
        iface = netif.get_interface(iface)
    except KeyError:
        middleware.logger.error('Internal interface %s not found, skipping setup.', iface)
        return

    carp1_addr = '169.254.10.20'
    carp2_addr = '169.254.10.80'

    found_i = found_1 = found_2 = False
    for address in iface.addresses:
        if address.af != netif.AddressFamily.INET:
            continue
        if str(address.address) == internal_ip:
            found_i = True
        elif str(address.address) == carp1_addr:
            found_1 = True
        elif str(address.address) == carp2_addr:
            found_2 = True
        else:
            iface.remove_address(address)

    # VHID needs to be configured before aliases
    found = 0
    for carp_config in iface.carp_config:
        if carp_config.vhid == 10 and carp_config.advskew == carp1_skew:
            found += 1
        elif carp_config.vhid == 20 and carp_config.advskew == carp2_skew:
            found += 1
        else:
            found -= 1
    if found != 2:
        iface.carp_config = [
            netif.CarpConfig(10, advskew=carp1_skew),
            netif.CarpConfig(20, advskew=carp2_skew),
        ]

    if not found_i:
        iface.add_address(middleware.call_sync('interface.alias_to_addr', {
            'address': internal_ip,
            'netmask': '24',
        }))

    if not found_1:
        iface.add_address(middleware.call_sync('interface.alias_to_addr', {
            'address': carp1_addr,
            'netmask': '32',
            'vhid': 10,
        }))

    if not found_2:
        iface.add_address(middleware.call_sync('interface.alias_to_addr', {
            'address': carp2_addr,
            'netmask': '32',
            'vhid': 20,
        }))


async def interface_pre_sync_hook(middleware):
    hardware = await middleware.call('failover.hardware')
    if hardware == 'MANUAL':
        middleware.logger.debug('No HA hardware detected, skipping interfaces setup.')
        return
    node = await middleware.call('failover.node')
    if node == 'A':
        carp1_skew = 20
        carp2_skew = 80
        internal_ip = '169.254.10.1'
    elif node == 'B':
        carp1_skew = 80
        carp2_skew = 20
        internal_ip = '169.254.10.2'
    else:
        middleware.logger.debug('Could not determine HA node, skipping interfaces setup.')
        return

    iface = await middleware.call('failover.internal_interfaces')
    if not iface:
        middleware.logger.debug(f'No internal interfaces found for {hardware}.')
        return
    iface = iface[0]

    await middleware.run_in_thread(
        sync_internal_ips, middleware, iface, carp1_skew, carp2_skew, internal_ip
    )


async def hook_restart_devd(middleware, *args, **kwargs):
    """
    We need to restart devd when SSH or UI settings are updated because of pf.conf.block rules
    might change.
    """
    if not await middleware.call('failover.licensed'):
        return
    await middleware.call('service.start', 'ix-devd')


async def hook_license_update(middleware, *args, **kwargs):
    if await middleware.call('failover.licensed'):
        etc_generate = ['rc']
        if await middleware.call('system.feature_enabled', 'FIBRECHANNEL'):
            await middleware.call('etc.generate', 'loader')
            etc_generate += ['loader']
        try:
            await middleware.call('failover.send_small_file', '/data/license')
            for etc in etc_generate:
                await middleware.call('falover.call_remote', 'etc.generate', [etc])
        except Exception:
            middleware.logger.warning('Failed to sync license file to standby.')


async def hook_setup_ha(middleware, *args, **kwargs):

    if not await middleware.call('failover.licensed'):
        return

    if not await middleware.call('interface.query', [('failover_vhid', '!=', None)]):
        return

    if not await middleware.call('pool.query'):
        return

    try:
        ha_configured = await middleware.call(
            'failover.call_remote', 'failover.status'
        ) != 'SINGLE'
    except Exception:
        ha_configured = False

    if ha_configured:
        return

    middleware.logger.info('[HA] Setting up')

    middleware.logger.debug('[HA] Synchronizing database and files')
    await middleware.call('notifier.failover_sync_peer', 'to')

    middleware.logger.debug('[HA] Configuring network on standby node')
    await middleware.call('failover.call_remote', 'interface.sync')
    try:
        await middleware.call('failover.call_remote', 'route.sync')
    except Exception as e:
        middleware.logger.warn('Failed to sync routes on standby node: %s', e)

    middleware.logger.debug('[HA] Restarting devd to enable failover')
    await middleware.call('failover.call_remote', 'service.start', ['ix-devd'])
    await middleware.call('failover.call_remote', 'service.restart', ['devd'])
    await middleware.call('service.start', 'ix-devd')
    await middleware.call('service.restart', 'devd')

    middleware.logger.info('[HA] Setup complete')

    middleware.send_event('failover.setup', 'ADDED', fields={})


async def hook_sync_geli(middleware, pool=None):
    """
    When a new volume is created we need to sync geli file.
    """
    if not pool.get('encryptkey_path'):
        return

    if not await middleware.call('failover.licensed'):
        return

    try:
        if await middleware.call(
            'failover.call_remote', 'failover.status'
        ) != 'BACKUP':
            return
    except Exception:
        return

    # TODO: failover_sync_peer is overkill as it will sync a bunch of other things
    await middleware.call('notifier.failover_sync_peer', 'to')


async def hook_pool_export(middleware, pool=None, *args, **kwargs):
    await middleware.call('enclosure.sync_zpool', pool)


async def hook_pool_lock(middleware, pool=None):
    await middleware.call('failover.encryption_clearkey')
    try:
        await middleware.call('failover.call_remote', 'failover.encryption_clearkey')
    except Exception as e:
        middleware.logger.warn('Failed to clear encryption key on standby node: %s', e)


async def hook_pool_rekey(middleware, pool=None):
    if not pool or not pool['encryptkey_path']:
        return
    try:
        await middleware.call('failover.send_small_file', pool['encryptkey_path'])
    except Exception as e:
        middleware.logger.warn('Failed to send encryptkey to standby node: %s', e)


async def service_remote(middleware, service, verb, options):
    """
    Most of service actions need to be replicated to the standby node so we don't lose
    too much time during failover regenerating things (e.g. users database)

    This is the middleware side of what legacy UI did on service changes.
    """
    if options.get('sync') is False:
        return
    # Skip if service is blacklisted or we are not MASTER
    if service in (
        'system',
        'webshell',
        'netdata',
        'smartd',
        'system_datasets',
    ) or await middleware.call('failover.status') != 'MASTER':
        return
    # Nginx should never be stopped on standby node
    if service == 'nginx' and verb == 'stop':
        return
    try:
        if options.get('wait') is True:
            await middleware.call('failover.call_remote', f'service.{verb}', [service, options])
        else:
            await middleware.call('failover.call_remote', 'core.bulk', [
                f'service.{verb}', [[service, options]]
            ])
    except Exception as e:
        if not (isinstance(e, CallError) and e.errno in (errno.ECONNREFUSED, errno.EHOSTDOWN)):
            middleware.logger.warn(f'Failed to run {verb}({service})', exc_info=True)


async def _event_system_ready(middleware, event_type, args):
    """
    Method called when system is ready to issue an event in case
    HA upgrade is pending.
    """
    if await middleware.call('failover.status') in ('MASTER', 'SINGLE'):
        return
    if await middleware.call('keyvalue.get', 'HA_UPGRADE', False):
        middleware.send_event('failover.upgrade_pending', 'ADDED', {
            'id': 'BACKUP', 'fields': {'pending': True},
        })


def setup(middleware):
    middleware.event_register('failover.upgrade_pending', textwrap.dedent('''\
        Sent when system is ready and HA upgrade is pending.

        It is expected the client will react by issuing `upgrade_finish` call
        at user will.'''))
    middleware.event_subscribe('system', _event_system_ready)
    middleware.register_hook('core.on_connect', ha_permission, sync=True)
    middleware.register_hook('disk.post_geli_passphrase', hook_geli_passphrase, sync=False)
    middleware.register_hook('interface.pre_sync', interface_pre_sync_hook, sync=True)
    middleware.register_hook('interface.post_sync', hook_setup_ha, sync=True)
    middleware.register_hook('pool.post_create_or_update', hook_setup_ha, sync=True)
    middleware.register_hook('pool.post_create_or_update', hook_sync_geli, sync=True)
    middleware.register_hook('pool.post_export', hook_pool_export, sync=True)
    middleware.register_hook('pool.post_import_pool', hook_setup_ha, sync=True)
    middleware.register_hook('pool.post_lock', hook_pool_lock, sync=True)
    middleware.register_hook('pool.rekey_done', hook_pool_rekey, sync=True)
    middleware.register_hook('ssh.post_update', hook_restart_devd, sync=False)
    middleware.register_hook('system.general.post_update', hook_restart_devd, sync=False)
    middleware.register_hook('system.post_license_update', hook_license_update, sync=False)
    middleware.register_hook('service.pre_action', service_remote, sync=False)
    asyncio.ensure_future(journal_ha(middleware))
