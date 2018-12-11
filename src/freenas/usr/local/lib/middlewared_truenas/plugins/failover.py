import asyncio
import base64
import errno
import netif
import os
import socket
import subprocess
import sys

from collections import defaultdict

from middlewared.client import Client, ClientException
from middlewared.schema import accepts, Bool, Dict, Int, List, Str
from middlewared.service import no_auth_required, private, CallError, ConfigService, ValidationErrors
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
from freenasUI.support.utils import get_license

INTERNAL_IFACE_NF = '/tmp/.failover_internal_iface_not_found'
SYNC_FILE = '/var/tmp/sync_failed'


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
            await run('fenced', 'force')

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
        license, error = get_license()
        if license is None or not license.system_serial_ha:
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
            proc = run('/usr/sbin/pciconf -lv | grep "card=0xa01f8086 chip=0x10d38086"')
            if not proc.stdout:
                if not os.path.exists(INTERNAL_IFACE_NF):
                    open(INTERNAL_IFACE_NF, 'w').close()
                return []
            return [proc.stdout.split('@')[0]]
        elif hardware == 'SBB':
            return ['ix0']
        elif hardware in ('ECHOWARP', 'PUMA'):
            return ['ntb0']
        elif hardware == 'ULTIMATE':
            return ['igb1']
        elif hardware == 'BHYVE':
            return ['em0']
        return []

    @no_auth_required
    @accepts()
    async def status(self):
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

        masters = []
        internal_interfaces = await self.middleware.call('failover.internal_interfaces')
        for iface in interfaces:
            if iface['name'] in internal_interfaces:
                continue
            if not iface['state']['carp_config']:
                continue
            if iface['state']['carp_config'][0]['state'] == 'MASTER':
                masters.append(iface['name'])

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
    def force_master(self):
        """
        Force this controller to become MASTER.
        """
        cp = subprocess.run(['fenced', 'force'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if cp.returncode != 0:
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
            self.middleware.call('failover.call_remote', 'system.reboot', [{'delay': 2}])

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
    @accepts()
    def disabled_reasons(self):
        """
        Returns a list of reasons why failover is not enabled/functional.

        NO_VOLUME - There are no pools configured.
        NO_VIP - There are no interfaces configured with Virtual IP.
        NO_SYSTEM_READY - Other controller has not finished booting.
        NO_PONG - Other controller is not communicable.
        NO_FAILOVER - Failover is administratively disabled.
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

        node = self.node()
        if node == 'A':
            remote = '169.254.10.2'
        elif node == 'B':
            remote = '169.254.10.1'
        else:
            raise CallError(f'Node {node} invalid for call_remote', errno.EBADRPC)
        try:
            # 860 is the iSCSI port and blocked by the failover script
            with Client(f'ws://{remote}:6000/websocket', reserved_ports=True, reserved_ports_blacklist=[860]) as c:
                return c.call(method, *args, **options)
        except ConnectionRefusedError:
            raise CallError('Connection refused', errno.ECONNREFUSED)
        except OSError as e:
            if e.errno in (errno.EHOSTDOWN, errno.ENETUNREACH) or isinstance(e, socket.timeout):
                raise CallError('Standby node is down', errno.EHOSTDOWN)
            raise
        except ClientException as e:
            raise CallError(str(e), e.errno)

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
        app.authenticated = True


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
                with Client() as c:
                    c.call('failover.call_remote', 'datastore.sql', [query, params])
                j.queries.remove(q)
            except ClientException as e:
                if e.errno == errno.EHOSTDOWN:
                    middleware.logger.trace('Skipping journal sync, node down')
                    break
                retries[str(q)] += 1
                if retries[str(q)] >= 2:
                    # No need to warn/log multiple times the same thing
                    continue
                middleware.logger.exception('Failed to run sql: %s', e)
                try:
                    if not os.path.exists(SYNC_FILE):
                        open(SYNC_FILE, 'w').close()
                except Exception:
                    pass
                break
            except Exception as e:
                middleware.logger.exception('Query %s has failed for unknown reasons', query)

        if len(list(j.queries)) == 0 and os.path.exists(SYNC_FILE):
            try:
                os.unlink(SYNC_FILE)
            except:
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


def setup(middleware):
    middleware.register_hook('core.on_connect', ha_permission, sync=True)
    middleware.register_hook('disk.post_geli_passphrase', hook_geli_passphrase, sync=False)
    middleware.register_hook('interface.pre_sync', interface_pre_sync_hook, sync=True)
    middleware.register_hook('interface.post_sync', hook_setup_ha, sync=True)
    middleware.register_hook('pool.post_create_or_update', hook_setup_ha, sync=True)
    middleware.register_hook('pool.post_create_or_update', hook_sync_geli, sync=True)
    middleware.register_hook('service.pre_action', service_remote, sync=False)
    asyncio.ensure_future(journal_ha(middleware))
