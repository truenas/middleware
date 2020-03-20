# Copyright (c) 2019 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

import asyncio
import base64
import errno
from lockfile import LockFile
import logging
try:
    import netif
except ImportError:
    netif = None
import os
import pickle
import queue
import re
import shutil
import socket
import subprocess
try:
    import sysctl
except ImportError:
    sysctl = None
import tempfile
import textwrap
import time

from functools import partial

from middlewared.schema import accepts, Bool, Dict, Int, NOT_PROVIDED, Str
from middlewared.service import (
    job, no_auth_required, pass_app, private, throttle, CallError, ConfigService, ValidationErrors,
)
import middlewared.sqlalchemy as sa
from middlewared.plugins.auth import AuthService, SessionManagerCredentials
from middlewared.plugins.config import FREENAS_DATABASE
from middlewared.plugins.datastore.connection import DatastoreService
from middlewared.plugins.system import SystemService

BUFSIZE = 256
INTERNAL_IFACE_NF = '/tmp/.failover_internal_iface_not_found'
FAILOVER_NEEDOP = '/tmp/.failover_needop'

logger = logging.getLogger('failover')


class LocalEscrowCtl:
    def __init__(self):
        server = '/tmp/escrowd.sock'
        connected = False
        retries = 5

        # Start escrowd on demand
        #
        # Attempt to connect the server;
        # if connection can not be established, startescrowd and
        # retry.
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.connect(server)
            connected = True
        except Exception:
            subprocess.Popen(['escrowd'])
            while retries > 0 and connected is False:
                try:
                    retries = retries - 1
                    sock.connect(server)
                    connected = True
                except Exception:
                    time.sleep(1)

        if not connected:
            raise RuntimeError('Can\'t connect to escrowd')

        data = sock.recv(BUFSIZE).decode()
        if data != '220 Ready, go ahead\n':
            raise RuntimeError('server didn\'t send welcome message')
        self.sock = sock

    def __enter__(self):
        return self

    def __exit__(self, typ, value, traceback):
        self.close()

    def setkey(self, passphrase):
        # Set key on local escrow daemon.
        command = f'SETKEY {passphrase}\n'
        self.sock.sendall(command.encode())
        data = self.sock.recv(BUFSIZE).decode()
        return (data == '250 setkey accepted.\n')

    def clear(self):
        # Clear key on local escrow daemon.
        command = 'CLEAR'
        self.sock.sendall(command.encode())
        data = self.sock.recv(BUFSIZE).decode()
        succeeded = (data == '200 clear succeeded.\n')
        open(FAILOVER_NEEDOP, 'w')
        return succeeded

    def shutdown(self):
        # Shutdown local escrow daemon.
        command = 'SHUTDOWN'
        self.sock.sendall(command.encode())
        data = self.sock.recv(BUFSIZE).decode()
        return (data == '250 Shutting down.\n')

    def getkey(self):
        # Get key from local escrow daemon. Returns None if not available.
        command = 'REVEAL'
        self.sock.sendall(command.encode())
        data = self.sock.recv(BUFSIZE).decode()
        lines = data.split('\n')
        if lines[0] == '404 No passphrase present':
            return None
        elif lines[0] == '200 Approved':
            if len(lines) > 2:
                data = lines[1]
            else:
                data = self.sock.recv(BUFSIZE).decode()
                data = data.split('\n')[0]
            return data
        else:
            # Should never happen.
            return None

    def status(self):
        # Get status of local escrow daemon.
        # True -- Have key; False -- No key.
        command = 'STATUS'
        self.sock.sendall(command.encode())
        data = self.sock.recv(BUFSIZE).decode()
        return data == '200 keyd\n'

    def close(self):
        try:
            if self.sock:
                self.sock.close()
        except OSError:
            pass

    def __del__(self):
        self.close()


class TruenasNodeSessionManagerCredentials(SessionManagerCredentials):
    pass


def throttle_condition(middleware, app, *args, **kwargs):
    # app is None means internal middleware call
    if app is None or (app and app.authenticated):
        return True, 'AUTHENTICATED'
    return False, None


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

    @private
    async def failover_extend(self, data):
        data['master'] = await self.middleware.call('failover.node') == data.pop('master_node')
        return data

    @accepts(Dict(
        'failover_update',
        Bool('disabled'),
        Int('timeout'),
        Bool('master', null=True),
        update=True,
    ))
    async def do_update(self, data):
        """
        Update failover state.

        `disabled` when true indicates that HA is disabled.
        `master` sets the state of current node. Standby node will have the opposite value.
        """
        master = data.pop('master', NOT_PROVIDED)

        old = await self.middleware.call('datastore.config', 'system.failover')

        new = old.copy()
        new.update(data)

        if master is not NOT_PROVIDED:
            if master is None:
                # The node making the call is the one we want to make it MASTER by default
                data['master_node'] = await self.middleware.call('failover.node')
            else:
                data['master_node'] = await self._master_node(master)

        verrors = ValidationErrors()
        if new['disabled'] is False:
            if not await self.middleware.call('interface.query', [('failover_critical', '=', True)]):
                verrors.add(
                    'failover_update.disabled',
                    'You need at least one critical interface to enable failover.',
                )
        verrors.check()

        await self.middleware.call('datastore.update', 'system.failover', new['id'], new)

        await self.middleware.call('service.restart', 'failover')

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

    @accepts()
    def licensed(self):
        """
        Checks whether this instance is licensed as a HA unit.
        """
        info = self.middleware.call_sync('system.info')
        if not info['license'] or not info['license']['system_serial_ha']:
            return False
        return True

    @private
    def ha_mode(self):
        if self.HA_MODE is None:
            self.HA_MODE = self._ha_mode()
        return self.HA_MODE

    @staticmethod
    def _ha_mode():
        hardware = None
        node = None

        proc = subprocess.Popen([
            'dmidecode',
            '-s', 'system-product-name',
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        manufacturer = proc.communicate()[0].strip()

        if manufacturer == b'BHYVE':
            hardware = 'BHYVE'
            proc = subprocess.Popen(
                ['/sbin/camcontrol', 'devlist'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            devlist = proc.communicate()[0].decode(errors='ignore')
            if proc.returncode == 0:
                if 'TrueNAS_A' in devlist:
                    node = 'A'
                elif 'TrueNAS_B' in devlist:
                    node = 'B'

        else:
            enclosures = ['/dev/' + enc for enc in os.listdir('/dev') if enc.startswith('ses')]
            for enclosure in enclosures:
                proc = subprocess.Popen([
                    '/usr/sbin/getencstat',
                    '-V', enclosure,
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                encstat = proc.communicate()[0].decode('utf8', 'ignore').strip()
                # The echostream E16 JBOD and the echostream Z-series chassis are the same piece
                # of hardware. One of the only ways to differentiate them is to look at the
                # enclosure elements in detail. The Z-series chassis identifies element 0x26
                # as SD_9GV12P1J_12R6K4.  The E16 does not.
                # The E16 identifies element 0x25 as NM_3115RL4WB66_8R5K5
                # We use this fact to ensure we are looking at the internal enclosure, not a shelf.
                # If we used a shelf to determine which node was A or B you could cause the nodes
                # to switch identities by switching the cables for the shelf.
                if re.search(r'SD_9GV12P1J_12R6K4', encstat, re.M):
                    hardware = 'ECHOSTREAM'
                    reg = re.search(r'3U20D-Encl-([AB])\'', encstat, re.M)
                    # In theory this should only be reached if we are dealing with
                    # an echostream, which renders the "if reg else None" irrelevent
                    node = reg.group(1) if reg else None
                    # We should never be able to find more than one of these
                    # but just in case we ever have a situation where there are
                    # multiple internal enclosures, we'll just stop at the first one
                    # we find.
                    if node:
                        break
                # Identify PUMA platform by one of enclosure names.
                elif re.search(r'Enclosure Name: CELESTIC (P3215-O|P3217-B)', encstat, re.M):
                    hardware = 'PUMA'
                    # Identify node by comparing addresses from SES and SMP.
                    # There is no exact match, but allocation seems sequential.
                    proc = subprocess.Popen([
                        '/sbin/camcontrol', 'smpphylist', enclosure, '-q'
                    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf8')
                    phylist = proc.communicate()[0].strip()
                    reg = re.search(r'ESCE A_(5[0-9A-F]{15})', encstat, re.M)
                    if reg:
                        addr = f'0x{(int(reg.group(1), 16) - 1):016x}'
                        if addr in phylist:
                            node = 'A'
                            break
                    reg = re.search(r'ESCE B_(5[0-9A-F]{15})', encstat, re.M)
                    if reg:
                        addr = f'0x{(int(reg.group(1), 16) - 1):016x}'
                        if addr in phylist:
                            node = 'B'
                            break
                else:
                    # Identify ECHOWARP platform by one of enclosure names.
                    reg = re.search(r'Enclosure Name: (ECStream|iX) 4024S([ps])', encstat, re.M)
                    if reg:
                        hardware = 'ECHOWARP'
                        # Identify node by the last symbol of the model name
                        if reg.group(2) == 'p':
                            node = 'A'
                            break
                        elif reg.group(2) == 's':
                            node = 'B'
                            break

        if node:
            return hardware, node

        proc = subprocess.Popen([
            'dmidecode',
            '-s', 'system-serial-number',
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf8')
        serial = proc.communicate()[0].split('\n', 1)[0].strip()

        license = SystemService._get_license()

        if license is not None:
            if license['system_serial'] == serial:
                node = 'A'
            elif license['system_serial_ha'] == serial:
                node = 'B'

        if node is None:
            return 'MANUAL', None

        if license['system_serial'] and license['system_serial_ha']:
            mode = None
            proc = subprocess.Popen([
                'dmidecode',
                '-s', 'baseboard-product-name',
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf8')
            board = proc.communicate()[0].split('\n', 1)[0].strip()
            # If we've gotten this far it's because we were unable to
            # identify ourselves via enclosure device.
            if board == 'X8DTS':
                hardware = 'SBB'
            elif board.startswith('X8'):
                hardware = 'ULTIMATE'
            else:
                mode = 'MANUAL', None

            if mode is None:
                mode = hardware, node
            return mode
        else:
            return 'MANUAL', None

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
        return self.ha_mode()[0]

    @accepts()
    def node(self):
        """
        Gets the node identification.
          A - First node
          B - Seconde Node
          MANUAL - could not be identified, its in manual mode
        """
        node = self.ha_mode()[1]
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
            return ['vtnet1']
        return []

    @private
    def internal_interfaces_notfound(self):
        return os.path.exists(INTERNAL_IFACE_NF)

    @private
    async def get_carp_states(self, interfaces=None):
        if interfaces is None:
            interfaces = await self.middleware.call('interface.query')
        masters, backups, inits = [], [], []
        internal_interfaces = await self.middleware.call('failover.internal_interfaces')
        critical_interfaces = [iface['int_interface']
                               for iface in await self.middleware.call('datastore.query', 'network.interfaces',
                                                                       [['int_critical', '=', True]])]
        for iface in interfaces:
            if iface['name'] in internal_interfaces:
                continue
            if iface['name'] not in critical_interfaces:
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
    @pass_app()
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
        status = await self._status(app)
        if status != self.LAST_STATUS:
            self.LAST_STATUS = status
            self.middleware.send_event('failover.status', 'CHANGED', fields={'status': status})
        return status

    async def _status(self, app):
        try:
            status = await self.middleware.call('cache.get', 'failover_status')
        except KeyError:
            status = await self._get_local_status(app)
            if status:
                await self.middleware.call('cache.put', 'failover_status', status, 300)

        if status:
            return status

        try:
            remote_imported = await self.middleware.call('failover.call_remote', 'pool.query', [
                [['status', '!=', 'OFFLINE']]
            ])
            # Other node has the pool
            if remote_imported:
                # check for carp MASTER (any) in remote?
                return 'BACKUP'
            # Other node has no pool
            else:
                # check for carp MASTER (none) in remote?
                return 'ERROR'
        except Exception as e:
            # Anything other than ClientException is unexpected and should be logged
            if not isinstance(e, CallError):
                self.logger.warn('Failed checking failover status', exc_info=True)
            return 'UNKNOWN'

    async def _get_local_status(self, app):
        interfaces = await self.middleware.call('interface.query')
        if not any(filter(lambda x: x['state']['carp_config'], interfaces)):
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

    @private
    async def status_refresh(self):
        await self.middleware.call('cache.pop', 'failover_status')
        # Kick a new status so it may be ready on next user call
        await self.middleware.call('failover.status')
        await self.middleware.call('failover.disabled_reasons')

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
    @pass_app()
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
        # Skip if we are already MASTER
        if self.middleware.call_sync('failover.status') == 'MASTER':
            return False
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
        self.logger.debug('Sending database to standby controller')
        self.middleware.call_sync('failover.send_database')
        self.logger.debug('Sending license and pwenc files')
        self.send_small_file('/data/license')
        self.send_small_file('/data/pwenc_secret')
        self.send_small_file('/root/.ssh/authorized_keys')

        for path in ('/data/geli',):
            if not os.path.exists(path) or not os.path.isdir(path):
                continue
            for f in os.listdir(path):
                fullpath = os.path.join(path, f)
                if not os.path.isfile(fullpath):
                    continue
                self.send_small_file(fullpath)

        self.middleware.call_sync('failover.call_remote', 'service.restart', ['failover'])

        if options['reboot']:
            self.middleware.call_sync('failover.call_remote', 'system.reboot', [{'delay': 2}])

    @accepts()
    def sync_from_peer(self):
        """
        Sync database and files from the other controller.
        """
        self.middleware.call_sync('failover.call_remote', 'failover.sync_to_peer')

    @private
    async def send_database(self):
        await self.middleware.run_in_executor(DatastoreService.thread_pool, self._send_database)

    def _send_database(self):
        # We are in the `DatastoreService` thread so until the end of this method an item that we put into `sql_queue`
        # will be the last one and no one else is able to write neither to the database nor to the journal.

        # Journal thread will see that this is special value and will clear journal.
        sql_queue.put(None)

        self.send_small_file(FREENAS_DATABASE, FREENAS_DATABASE + '.sync')
        self.middleware.call_sync('failover.call_remote', 'failover.receive_database')

    @private
    def receive_database(self):
        os.rename(FREENAS_DATABASE + '.sync', FREENAS_DATABASE)
        self.middleware.call_sync('datastore.setup')

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
    @pass_app()
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
        reasons = set(self._disabled_reasons(app))
        if reasons != self.LAST_DISABLEDREASONS:
            self.LAST_DISABLEDREASONS = reasons
            self.middleware.send_event('failover.disabled_reasons', 'CHANGED', fields={'disabled_reasons': list(reasons)})
        return list(reasons)

    def _disabled_reasons(self, app):
        reasons = []
        if not self.middleware.call_sync('pool.query'):
            reasons.append('NO_VOLUME')
        if not any(filter(
            lambda x: x.get('failover_virtual_aliases'), self.middleware.call_sync('interface.query'))
        ):
            reasons.append('NO_VIP')
        try:
            assert self.middleware.call_sync('failover.remote_connected') is True
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
        except Exception:
            reasons.append('NO_PONG')
        if self.middleware.call_sync('failover.config')['disabled']:
            reasons.append('NO_FAILOVER')
        return reasons

    @private
    async def mismatch_disks(self):
        """
        On HA systems, da#'s can be different
        between controllers. This isn't common
        but does occurr. An example being when
        a customer powers off passive storage controller
        for maintenance and also powers off an expansion shelf.
        The active controller will reassign da#'s appropriately
        depending on which shelf was powered off. When passive
        storage controller comes back online, the da#'s will be
        different than what's on the active controller because the
        kernel reassigned those da#'s. This function now grabs
        the serial numbers of each disk and calculates the difference
        between the controllers. Instead of returning da#'s to alerts,
        this returns serial numbers.
        This accounts for 2 scenarios:
         1. the quantity of disks are different between
            controllers
         2. the quantity of disks are the same between
            controllers but serials do not match
        """
        local_boot_disks = await self.middleware.call('zfs.pool.get_disks', 'freenas-boot')
        remote_boot_disks = await self.middleware.call('failover.call_remote', 'zfs.pool.get_disks', ['freenas-boot'])
        local_disks = set(
            v['ident']
            for k, v in (await self.middleware.call('device.get_info', 'DISK')).items()
            if k not in local_boot_disks
        )
        remote_disks = set(
            v['ident']
            for k, v in (await self.middleware.call('failover.call_remote', 'device.get_info', ['DISK'])).items()
            if k not in remote_boot_disks
        )
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
    @accepts()
    def encryption_getkey(self):
        # FIXME: we could get rid of escrow, middlewared can do that job
        with LocalEscrowCtl() as escrowctl:
            return escrowctl.getkey()

    @private
    def encryption_shutdown(self):
        with LocalEscrowCtl() as escrowctl:
            return escrowctl.shutdown()

    @private
    def encryption_status(self):
        with LocalEscrowCtl() as escrowctl:
            return escrowctl.status()

    @private
    @accepts(Str('passphrase'), Dict('options', Bool('sync', default=True)))
    def encryption_setkey(self, passphrase, options=None):
        # FIXME: we could get rid of escrow, middlewared can do that job
        with LocalEscrowCtl() as escrowctl:
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
        with LocalEscrowCtl() as escrowctl:
            return escrowctl.clear()

    @private
    @job()
    def encryption_attachall(self, job):
        pools = self.middleware.call_sync('pool.query', [('encrypt', '>', 0)])
        if not pools:
            return
        with LocalEscrowCtl() as escrowctl, tempfile.NamedTemporaryFile(mode='w+') as tmp:
            tmp.file.write(escrowctl.getkey() or "")
            tmp.file.flush()
            procs = []
            failed_drive = 0
            failed_volume = 0
            for pool in pools:
                keyfile = pool['encryptkey_path']
                for encrypted_disk in self.middleware.call_sync(
                    'datastore.query',
                    'storage.encrypteddisk',
                    [('encrypted_volume', '=', pool['id'])]
                ):

                    if encrypted_disk['encrypted_disk']:
                        # gptid might change on the active head, so we need to rescan
                        # See #16070
                        try:
                            open(
                                f'/dev/{encrypted_disk["encrypted_disk"]["disk_name"]}', 'w'
                            ).close()
                        except Exception:
                            self.logger.warning(
                                'Failed to open dev %s to rescan.',
                                encrypted_disk['encrypted_disk']['name'],
                            )
                    provider = encrypted_disk['encrypted_provider']
                    if not os.path.exists(f'/dev/{provider}.eli'):
                        proc = subprocess.Popen(
                            'geli attach {} -k {} {}'.format(
                                f'-j {tmp.name}' if pool['encrypt'] == 2 else '-p',
                                keyfile,
                                provider,
                            ),
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            shell=True,
                        )
                        procs.append(proc)
                for proc in procs:
                    msg = proc.communicate()[1]
                    if proc.returncode != 0:
                        job.set_progress(None, f'Unable to attach GELI provider: {msg}')
                        self.logger.warn('Unable to attach GELI provider: %s', msg)
                        failed_drive += 1

                job = self.middleware.call_sync('zfs.pool.import', pool['guid'], {
                    'altroot': '/mnt',
                })
                job.wait_sync()
                if job.error:
                    failed_volume += 1

            if failed_drive > 0:
                job.set_progress(None, f'{failed_drive} can not be attached.')
                self.logger.error('%d can not be attached.', failed_drive)

            try:
                if failed_volume == 0:
                    try:
                        os.unlink(FAILOVER_NEEDOP)
                    except FileNotFoundError:
                        pass
                    passphrase = escrowctl.getkey()
                    try:
                        self.middleware.call_sync(
                            'failover.call_remote', 'failover.encryption_setkey', [passphrase]
                        )
                    except Exception:
                        self.logger.error(
                            'Failed to set encryption key on standby node.', exc_info=True,
                        )
                else:
                    open(FAILOVER_NEEDOP, 'w').close()
            except Exception:
                pass

    @private
    @job()
    def encryption_detachall(self, job):
        # Let us be very careful before we rip down the GELI providers
        for pool in self.middleware.call_sync('pool.query', [('encrypt', '>', 0)]):
            if pool['status'] == 'OFFLINE':
                for encrypted_disk in self.middleware.call_sync(
                    'datastore.query',
                    'storage.encrypteddisk',
                    [('encrypted_volume', '=', pool['id'])]
                ):
                    provider = encrypted_disk['encrypted_provider']
                    cp = subprocess.run(
                        ['geli', 'detach', provider],
                        capture_output=True, text=True, check=False,
                    )
                    if cp.returncode != 0:
                        job.set_progress(
                            None,
                            f'Unable to detach GELI provider {provider}: {cp.stderr}',
                        )
                return True
            else:
                job.set_progress(
                    None,
                    'Not detaching GELI providers because an encrypted zpool with name '
                    f'{pool["name"]!r} is still mounted!',
                )
                return False

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

        failover = await self.middleware.call('datastore.config', 'system.failover')
        if action == 'ENABLE':
            if failover['disabled'] is False:
                # Already enabled
                return False
            update = {
                'disabled': False,
                'master_node': await self._master_node(False),
            }
            await self.middleware.call('datastore.update', 'system.failover', failover['id'], update)
            await self.middleware.call('service.restart', 'failover')
        elif action == 'DISABLE':
            if failover['disabled'] is True:
                # Already disabled
                return False
            update = {
                'master_node': await self._master_node(True if options.get('active') else False),
            }
            await self.middleware.call('datastore.update', 'system.failover', failover['id'], update)
            await self.middleware.call('service.restart', 'failover')

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

        try:
            if not self.middleware.call_sync('failover.call_remote', 'system.ready'):
                raise CallError('Standby Controller is not ready, wait boot process.')

            legacy_upgrade = False
            try:
                self.middleware.call_sync('failover.call_remote', 'failover.upgrade_version')
            except CallError as e:
                if e.errno == CallError.ENOMETHOD:
                    legacy_upgrade = True
                else:
                    raise

            if not updatefile and not legacy_upgrade:
                def download_callback(j):
                    job.set_progress(
                        None, j['progress']['description'] or 'Downloading upgrade files'
                    )

                djob = self.middleware.call_sync('update.download', job_on_progress_cb=download_callback)
                djob.wait_sync()
                if djob.error:
                    raise CallError(f'Error downloading update: {djob.error}')
                if not djob.result:
                    raise CallError('No updates available.')

            self.middleware.call_sync('keyvalue.set', 'HA_UPGRADE', True)

            if legacy_upgrade:
                namespace = 'notifier'
            else:
                namespace = 'update'
            self.middleware.call_sync('failover.call_remote', f'{namespace}.destroy_upload_location')
            remote_path = self.middleware.call_sync(
                'failover.call_remote', f'{namespace}.create_upload_location'
            ) or '/var/tmp/firmware'

            # Only send files to standby:
            # 1. Its a manual upgrade which means it needs to go through master first
            # 2. Its not a legacy upgrade, which means files are downloaded on master first
            #
            # For legacy upgrade it will be downloaded directly from standby.
            if updatefile or not legacy_upgrade:
                job.set_progress(None, 'Sending files to Standby Controller')
                token = self.middleware.call_sync('failover.call_remote', 'auth.generate_token')

                for f in os.listdir(local_path):
                    self.middleware.call_sync('failover.sendfile', token, os.path.join(local_path, f), os.path.join(remote_path, f))

            local_version = self.middleware.call_sync('system.version')
            remote_version = self.middleware.call_sync('failover.call_remote', 'system.version')

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

            # If they are the same we assume this is a clean upgrade so we start by
            # upgrading the standby controller.
            if legacy_upgrade or local_version == remote_version:
                rjob = self.middleware.call_sync(
                    'failover.call_remote', update_method, update_remote_args, {
                        'job_return': True,
                        'callback': partial(callback, controller='REMOTE')
                    }
                )
            else:
                rjob = None

            if not legacy_upgrade:
                ljob = self.middleware.call_sync(
                    update_method, *update_local_args,
                    job_on_progress_cb=partial(callback, controller='LOCAL')
                )
                ljob.wait_sync()
                if ljob.error:
                    raise CallError(ljob.error)

                remote_boot_id = self.middleware.call_sync(
                    'failover.call_remote', 'system.boot_id'
                )

            if rjob:
                rjob.result()

            self.middleware.call_sync('failover.call_remote', 'system.reboot', [
                {'delay': 5}
            ], {'job': True})

        except Exception:
            raise

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
            retry_time = time.monotonic()
            shutdown_timeout = sysctl.filter('kern.init_shutdown_timeout')[0].value
            while time.monotonic() - retry_time < shutdown_timeout:
                self.middleware.call_sync('failover.call_remote', 'core.ping', [], {'timeout': 5})
                time.sleep(5)
        except CallError:
            pass
        else:
            raise CallError('Standby Controller failed to reboot.', errno.ETIMEDOUT)

        if not self.upgrade_waitstandby():
            raise CallError('Timed out waiting Standby Controller after upgrade.')

        if not legacy_upgrade and remote_boot_id == self.middleware.call_sync(
            'failover.call_remote', 'system.boot_id'
        ):
            raise CallError('Standby Controller failed to reboot.')

        return True

    @private
    def upgrade_waitstandby(self, seconds=900):
        """
        We will wait up to 15 minutes by default for the Standby Controller to reboot.
        This values come from observation from support of how long a M-series can take.
        """
        retry_time = time.monotonic()
        while time.monotonic() - retry_time < seconds:
            try:
                if not self.middleware.call_sync('failover.call_remote', 'system.ready'):
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
            assert self.call_remote('core.ping') == 'pong'
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


async def hook_geli_passphrase(middleware, passphrase):
    """
    Hook to set pool passphrase when its changed.
    """
    if not await middleware.call('failover.licensed'):
        return
    if passphrase:
        await middleware.call('failover.encryption_setkey', passphrase, {'sync': True})
    else:
        await middleware.call('failover.encryption_clearkey')


sql_queue = queue.Queue()


class Journal:
    path = '/data/ha-journal'

    def __init__(self):
        self.journal = []
        if os.path.exists(self.path):
            try:
                with open(self.path, 'rb') as f:
                    self.journal = pickle.load(f)
            except Exception:
                logger.warning('Failed to read journal', exc_info=True)

        self.persisted_journal = self.journal.copy()

    def __bool__(self):
        return bool(self.journal)

    def __iter__(self):
        for query, params in self.journal:
            yield query, params

    def __len__(self):
        return len(self.journal)

    def peek(self):
        return self.journal[0]

    def shift(self):
        self.journal = self.journal[1:]

    def append(self, item):
        self.journal.append(item)

    def clear(self):
        self.journal = []

    def write(self):
        if self.persisted_journal != self.journal:
            self._write()
            self.persisted_journal = self.journal.copy()

    def _write(self):
        tmp_file = f'{self.path}.tmp'

        with open(tmp_file, 'wb') as f:
            pickle.dump(self.journal, f)

        os.rename(tmp_file, self.path)


class JournalSync:
    def __init__(self, middleware, sql_queue, journal):
        self.middleware = middleware
        self.sql_queue = sql_queue
        self.journal = journal

        self.failover_status = None
        self._update_failover_status()

        self.last_query_failed = False  # this only affects logging

    def process(self):
        if self.failover_status != 'MASTER':
            if self.journal:
                logger.warning('Node status %s but has %d queries in journal', self.failover_status, len(self.journal))

            self.journal.clear()

        had_journal_items = bool(self.journal)
        flush_succeeded = self._flush_journal()

        if had_journal_items:
            # We've spent some flushing journal, failover status might have changed
            self._update_failover_status()

        self._consume_queue_nonblocking()
        self.journal.write()

        # Avoid busy loop
        if flush_succeeded:
            # The other node is synchronized, we can wait until new query arrives
            timeout = None
        else:
            # Retry in N seconds,
            timeout = 5

        try:
            item = sql_queue.get(True, timeout)
        except queue.Empty:
            pass
        else:
            # We've spent some time waiting, failover status might have changed
            self._update_failover_status()

            self._handle_sql_queue_item(item)

            # Consume other pending queries
            self._consume_queue_nonblocking()

        self.journal.write()

    def _flush_journal(self):
        while self.journal:
            query, params = self.journal.peek()

            try:
                self.middleware.call_sync('failover.call_remote', 'datastore.sql', [query, params])
            except Exception as e:
                if isinstance(e, CallError) and e.errno in [errno.ECONNREFUSED, errno.EHOSTDOWN]:
                    logger.trace('Skipping journal sync, node down')
                else:
                    if not self.last_query_failed:
                        logger.exception('Failed to run query %s: %r', query, e)
                        self.last_query_failed = True

                    self.middleware.call_sync('alert.oneshot_create', 'FailoverSyncFailed', None)

                return False
            else:
                self.last_query_failed = False

                self.middleware.call_sync('alert.oneshot_delete', 'FailoverSyncFailed', None)

                self.journal.shift()

        return True

    def _consume_queue_nonblocking(self):
        while True:
            try:
                self._handle_sql_queue_item(self.sql_queue.get_nowait())
            except queue.Empty:
                break

    def _handle_sql_queue_item(self, item):
        if item is None:
            # This is sent by `failover.send_database`
            self.journal.clear()
        else:
            if self.failover_status == 'SINGLE':
                pass
            elif self.failover_status == 'MASTER':
                self.journal.append(item)
            else:
                query, params = item
                logger.warning('Node status %s but executed SQL query: %s', self.failover_status, query)

    def _update_failover_status(self):
        self.failover_status = self.middleware.call_sync('failover.status')


def hook_datastore_execute_write(middleware, sql, params):
    sql_queue.put((sql, params))


async def journal_ha(middleware):
    """
    This is a green thread responsible for trying to sync the journal
    file to the other node.
    Every SQL query that could not be synced is stored in the journal.
    """
    await middleware.run_in_thread(journal_sync, middleware)


def journal_sync(middleware):
    while True:
        try:
            journal = Journal()
            journal_sync = JournalSync(middleware, sql_queue, journal)
            while True:
                journal_sync.process()
        except Exception:
            logger.warning('Failed to sync journal', exc_info=True)
            time.sleep(5)


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
    await middleware.call('service.restart', 'failover')


async def hook_license_update(middleware, *args, **kwargs):
    FailoverService.HA_MODE = None
    if await middleware.call('failover.licensed'):
        await middleware.call('failover.ensure_remote_client')
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
    await middleware.call('service.restart', 'failover')
    await middleware.call('failover.status_refresh')


async def hook_setup_ha(middleware, *args, **kwargs):

    if not await middleware.call('failover.licensed'):
        return

    if not await middleware.call('interface.query', [('failover_vhid', '!=', None)]):
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
        # If HA is already configured just sync network
        if await middleware.call('failover.status') == 'MASTER':
            middleware.logger.debug('[HA] Configuring network on standby node')
            await middleware.call('failover.call_remote', 'interface.sync')
        return

    middleware.logger.info('[HA] Setting up')

    middleware.logger.debug('[HA] Synchronizing database and files')
    await middleware.call('failover.sync_to_peer')

    middleware.logger.debug('[HA] Configuring network on standby node')
    await middleware.call('failover.call_remote', 'interface.sync')

    middleware.logger.debug('[HA] Restarting devd to enable failover')
    await middleware.call('failover.call_remote', 'service.restart', ['failover'])
    await middleware.call('service.restart', 'failover')

    await middleware.call('failover.status_refresh')

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
    await middleware.call('failover.sync_to_peer')


async def hook_pool_export(middleware, pool=None, *args, **kwargs):
    await middleware.call('enclosure.sync_zpool', pool)


async def hook_pool_lock(middleware, pool=None):
    await middleware.call('failover.encryption_clearkey')
    try:
        await middleware.call('failover.call_remote', 'failover.encryption_clearkey')
    except Exception as e:
        middleware.logger.warn('Failed to clear encryption key on standby node: %s', e)


async def hook_pool_unlock(middleware, pool=None, passphrase=None):
    if passphrase:
        await middleware.call('failover.encryption_setkey', passphrase)


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
    if not options['ha_propagate']:
        return
    # Skip if service is blacklisted or we are not MASTER
    if service in (
        'system',
        'webshell',
        'smartd',
        'system_datasets',
        'nfs',
    ) or await middleware.call('failover.status') != 'MASTER':
        return
    # Nginx should never be stopped on standby node
    if service == 'nginx' and verb == 'stop':
        return
    try:
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


def remote_status_event(middleware, *args, **kwargs):
    middleware.call_sync('failover.status_refresh')


async def setup(middleware):
    middleware.event_register('failover.status', 'Sent when failover status changes.')
    middleware.event_register(
        'failover.disabled_reasons',
        'Sent when the reasons for failover being disabled have changed.'
    )
    middleware.event_register('failover.upgrade_pending', textwrap.dedent('''\
        Sent when system is ready and HA upgrade is pending.

        It is expected the client will react by issuing `upgrade_finish` call
        at user will.'''))
    middleware.event_subscribe('system', _event_system_ready)
    middleware.register_hook('core.on_connect', ha_permission, sync=True)
    middleware.register_hook('datastore.post_execute_write', hook_datastore_execute_write, inline=True)
    middleware.register_hook('disk.post_geli_passphrase', hook_geli_passphrase, sync=False)
    middleware.register_hook('interface.pre_sync', interface_pre_sync_hook, sync=True)
    middleware.register_hook('interface.post_sync', hook_setup_ha, sync=True)
    middleware.register_hook('pool.post_create_or_update', hook_setup_ha, sync=True)
    middleware.register_hook('pool.post_create_or_update', hook_sync_geli, sync=True)
    middleware.register_hook('pool.post_export', hook_pool_export, sync=True)
    middleware.register_hook('pool.post_import', hook_setup_ha, sync=True)
    middleware.register_hook('pool.post_lock', hook_pool_lock, sync=True)
    middleware.register_hook('pool.post_unlock', hook_pool_unlock, sync=True)
    middleware.register_hook('pool.rekey_done', hook_pool_rekey, sync=True)
    middleware.register_hook('ssh.post_update', hook_restart_devd, sync=False)
    middleware.register_hook('system.general.post_update', hook_restart_devd, sync=False)
    middleware.register_hook('system.post_license_update', hook_license_update, sync=False)
    middleware.register_hook('service.pre_action', service_remote, sync=False)

    # Register callbacks to properly refresh HA status and send events on changes
    await middleware.call('failover.remote_subscribe', 'system', remote_status_event)
    await middleware.call('failover.remote_subscribe', 'failover.carp_event', remote_status_event)
    await middleware.call('failover.remote_on_connect', remote_status_event)
    await middleware.call('failover.remote_on_disconnect', remote_status_event)

    asyncio.ensure_future(journal_ha(middleware))
