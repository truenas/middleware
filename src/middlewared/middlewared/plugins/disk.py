import asyncio
import base64
from collections import defaultdict
import errno
import glob
import os
import re
import subprocess
try:
    import sysctl
except ImportError:
    sysctl = None
import tempfile

try:
    from bsd import geom
except ImportError:
    geom = None

from middlewared.schema import accepts, Bool, Dict, Int, Str
from middlewared.service import private, CallError, CRUDService
from middlewared.service_exception import ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils import Popen, run
from middlewared.utils.asyncio_ import asyncio_map


GELI_KEY_SLOT = 0
GELI_RECOVERY_SLOT = 1
GELI_REKEY_FAILED = '/tmp/.rekey_failed'
RE_CAMCONTROL_AAM = re.compile(r'^automatic acoustic management\s+yes', re.M)
RE_CAMCONTROL_APM = re.compile(r'^advanced power management\s+yes', re.M)
RE_CAMCONTROL_DRIVE_LOCKED = re.compile(r'^drive locked\s+yes$', re.M)
RE_CAMCONTROL_POWER = re.compile(r'^power management\s+yes', re.M)
RE_DA = re.compile('^da[0-9]+$')
RE_ISDISK = re.compile(r'^(da|ada|vtbd|mfid|nvd|pmem)[0-9]+$')
RE_MPATH_NAME = re.compile(r'[a-z]+(\d+)')
RE_SED_RDLOCK_EN = re.compile(r'(RLKEna = Y|ReadLockEnabled:\s*1)', re.M)
RE_SED_WRLOCK_EN = re.compile(r'(WLKEna = Y|WriteLockEnabled:\s*1)', re.M)


class DiskModel(sa.Model):
    __tablename__ = 'storage_disk'

    disk_identifier = sa.Column(sa.String(42), primary_key=True)
    disk_name = sa.Column(sa.String(120))
    disk_subsystem = sa.Column(sa.String(10), default='')
    disk_number = sa.Column(sa.Integer(), default=1)
    disk_serial = sa.Column(sa.String(30))
    disk_size = sa.Column(sa.String(20))
    disk_multipath_name = sa.Column(sa.String(30))
    disk_multipath_member = sa.Column(sa.String(30))
    disk_description = sa.Column(sa.String(120))
    disk_transfermode = sa.Column(sa.String(120), default="Auto")
    disk_hddstandby = sa.Column(sa.String(120), default="Always On")
    disk_hddstandby_force = sa.Column(sa.Boolean(), default=False)
    disk_advpowermgmt = sa.Column(sa.String(120), default="Disabled")
    disk_acousticlevel = sa.Column(sa.String(120), default="Disabled")
    disk_togglesmart = sa.Column(sa.Boolean(), default=True)
    disk_smartoptions = sa.Column(sa.String(120))
    disk_expiretime = sa.Column(sa.DateTime(), nullable=True)
    disk_enclosure_slot = sa.Column(sa.Integer(), nullable=True)
    disk_passwd = sa.Column(sa.EncryptedText(), default='')
    disk_critical = sa.Column(sa.Integer(), nullable=True, default=None)
    disk_difference = sa.Column(sa.Integer(), nullable=True, default=None)
    disk_informational = sa.Column(sa.Integer(), nullable=True, default=None)
    disk_model = sa.Column(sa.String(200), nullable=True, default=None)
    disk_rotationrate = sa.Column(sa.Integer(), nullable=True, default=None)
    disk_type = sa.Column(sa.String(20), default='UNKNOWN')
    disk_kmip_uid = sa.Column(sa.String(255), nullable=True, default=None)


class DiskService(CRUDService):

    class Config:
        datastore = 'storage.disk'
        datastore_prefix = 'disk_'
        datastore_extend = 'disk.disk_extend'
        datastore_filters = [('expiretime', '=', None)]
        datastore_extend_context = 'disk.disk_extend_context'

    @private
    async def disk_extend(self, disk, context):
        disk.pop('enabled', None)
        for key in ['acousticlevel', 'advpowermgmt', 'hddstandby']:
            disk[key] = disk[key].upper()
        try:
            disk['size'] = int(disk['size'])
        except ValueError:
            disk['size'] = None
        if disk['multipath_name']:
            disk['devname'] = f'multipath/{disk["multipath_name"]}'
        else:
            disk['devname'] = disk['name']
        self._expand_enclosure(disk)
        if context['passwords']:
            if not disk['passwd']:
                disk['passwd'] = context['disks_keys'].get(disk['identifier'], '')
        else:
            disk.pop('passwd')
            disk.pop('kmip_uid')
        return disk

    @private
    async def disk_extend_context(self, extra):
        context = {'passwords': extra.get('passwords', False), 'disks_keys': {}}
        if extra.get('passwords'):
            context['disks_keys'] = await self.middleware.call('kmip.retrieve_sed_disks_keys')
        return context

    def _expand_enclosure(self, disk):
        if disk['enclosure_slot'] is not None:
            disk['enclosure'] = {
                'number': disk['enclosure_slot'] // 1000,
                'slot': disk['enclosure_slot'] % 1000
            }
        else:
            disk['enclosure'] = None
        del disk['enclosure_slot']

    def _compress_enclosure(self, disk):
        if disk['enclosure'] is not None:
            disk['enclosure_slot'] = disk['enclosure']['number'] * 1000 + disk['enclosure']['slot']
        else:
            disk['enclosure_slot'] = None
        del disk['enclosure']

    @accepts(
        Str('id'),
        Dict(
            'disk_update',
            Bool('togglesmart'),
            Str('acousticlevel', enum=[
                'DISABLED', 'MINIMUM', 'MEDIUM', 'MAXIMUM'
            ]),
            Str('advpowermgmt', enum=[
                'DISABLED', '1', '64', '127', '128', '192', '254'
            ]),
            Str('description'),
            Str('hddstandby', enum=[
                'ALWAYS ON', '5', '10', '20', '30', '60', '120', '180', '240', '300', '330'
            ]),
            Bool('hddstandby_force'),
            Str('passwd', private=True),
            Str('smartoptions'),
            Int('critical', null=True),
            Int('difference', null=True),
            Int('informational', null=True),
            Dict(
                'enclosure',
                Int('number'),
                Int('slot'),
                null=True,
            ),
            update=True
        )
    )
    async def do_update(self, id, data):
        """
        Update disk of `id`.

        If extra options need to be passed to SMART which we don't already support, they can be passed by
        `smartoptions`.

        `critical`, `informational` and `difference` are integer values on which alerts for SMART are configured
        if the disk temperature crosses the assigned threshold for each respective attribute.
        If they are set to null, then SMARTD config values are used as defaults.

        Email of log level LOG_CRIT is issued when disk temperature crosses `critical`.

        Email of log level LOG_INFO is issued when disk temperature crosses `informational`.

        If temperature of a disk changes by `difference` degree Celsius since the last report, SMART reports this.
        """

        old = await self.middleware.call(
            'datastore.query', 'storage.disk', [['identifier', '=', id]], {
                'get': True, 'prefix': self._config.datastore_prefix
            }
        )
        old.pop('enabled', None)
        self._expand_enclosure(old)
        new = old.copy()
        new.update(data)

        verrors = ValidationErrors()

        if new['hddstandby_force']:
            if new['hddstandby'] == 'ALWAYS ON':
                verrors.add(
                    'disk_update.hddstandby_force',
                    'This option does not have sense when HDD Standby is not set'
                )

        if verrors:
            raise verrors

        if not new['passwd'] and old['passwd'] != new['passwd']:
            # We want to make sure kmip uid is None in this case
            if new['kmip_uid']:
                asyncio.ensure_future(self.middleware.call('kmip.reset_sed_disk_password', id, new['kmip_uid']))
            new['kmip_uid'] = None

        for key in ['acousticlevel', 'advpowermgmt', 'hddstandby']:
            new[key] = new[key].title()

        self._compress_enclosure(new)

        await self.middleware.call(
            'datastore.update',
            self._config.datastore,
            id,
            new,
            {'prefix': self._config.datastore_prefix}
        )

        if any(new[key] != old[key] for key in ['hddstandby', 'advpowermgmt', 'acousticlevel']):
            await self.middleware.call('disk.power_management', new['name'])

        if any(
            new[key] != old[key]
            for key in [
                'togglesmart', 'smartoptions', 'hddstandby', 'hddstandby_force',
                'critical', 'difference', 'informational',
            ]
        ):
            if new['togglesmart']:
                await self.middleware.call('disk.toggle_smart_on', new['name'])
            else:
                await self.middleware.call('disk.toggle_smart_off', new['name'])

            await self.middleware.call('disk.update_hddstandby_force')
            await self.middleware.call('disk.update_smartctl_args_for_disks')
            await self.middleware.call('service.restart', 'collectd')
            await self._service_change('smartd', 'restart')
            await self._service_change('snmp', 'restart')

        if new['passwd'] and old['passwd'] != new['passwd']:
            await self.middleware.call('kmip.sync_sed_keys', [id])

        return await self.query([['identifier', '=', id]], {'get': True})

    @private
    def get_name(self, disk):
        if disk["multipath_name"]:
            return f"multipath/{disk['multipath_name']}"
        else:
            return disk["name"]

    @accepts(Bool("join_partitions", default=False))
    async def get_unused(self, join_partitions):
        """
        Helper method to get all disks that are not in use, either by the boot
        pool or the user pools.
        """
        disks = await self.query([('devname', 'nin', await self.get_reserved())])

        if join_partitions:
            for disk in disks:
                disk["partitions"] = await self.__get_partitions(disk)

        return disks

    @accepts(Dict(
        'options',
        Bool('unused', default=False),
    ))
    def get_encrypted(self, options):
        """
        Get all geli providers

        It might be an entire disk or a partition of type freebsd-zfs
        """
        providers = []

        disks_blacklist = []
        if options['unused']:
            disks_blacklist += self.middleware.call_sync('disk.get_reserved')

        geom.scan()
        klass_part = geom.class_by_name('PART')
        klass_label = geom.class_by_name('LABEL')
        if not klass_part:
            return providers

        for g in klass_part.geoms:
            for p in g.providers:

                if p.config['type'] != 'freebsd-zfs':
                    continue

                disk = p.geom.consumer.provider.name
                if disk in disks_blacklist:
                    continue

                try:
                    subprocess.run(
                        ['geli', 'dump', p.name],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True,
                    )
                except subprocess.CalledProcessError:
                    continue

                dev = None
                if klass_label:
                    for g in klass_label.geoms:
                        if g.name == p.name:
                            dev = g.provider.name
                            break

                if dev is None:
                    dev = p.name

                providers.append({
                    'name': p.name,
                    'dev': dev,
                    'disk': disk
                })

        return providers

    @private
    def geli_attach(self, pool, passphrase=None, key=None):
        """
        Attach geli providers of a given pool

        Returns:
            The number of providers that failed to attach
        """
        failed = 0
        geli_keyfile = key or pool['encryptkey_path']

        if passphrase:
            passf = tempfile.NamedTemporaryFile(mode='w+', dir='/tmp/')
            os.chmod(passf.name, 0o600)
            passf.write(passphrase)
            passf.flush()
            passphrase = passf.name
        try:
            for ed in self.middleware.call_sync(
                'datastore.query', 'storage.encrypteddisk', [('encrypted_volume', '=', pool['id'])]
            ):
                dev = ed['encrypted_provider']
                try:
                    self.middleware.call_sync('disk.geli_attach_single', dev, geli_keyfile, passphrase)
                except Exception as ee:
                    self.logger.warn(str(ee))
                    failed += 1
        finally:
            if passphrase:
                passf.close()
        return failed

    @private
    def geli_testkey(self, pool, passphrase):
        """
        Test key for geli providers of a given pool

        Returns:
            bool
        """

        with tempfile.NamedTemporaryFile(mode='w+', dir='/tmp') as tf:
            os.chmod(tf.name, 0o600)
            tf.write(passphrase)
            tf.flush()
            # EncryptedDisk table might be out of sync for some reason,
            # this is much more reliable!
            devs = self.middleware.call_sync('zfs.pool.get_devices', pool['name'])
            for dev in devs:
                name, ext = os.path.splitext(dev)
                if ext != '.eli':
                    continue
                try:
                    self.middleware.call_sync(
                        'disk.geli_attach_single', name, pool['encryptkey_path'],
                        tf.name if passphrase else None, True,
                    )
                except Exception as e:
                    # "Missing -p flag" happens when using passphrase on a pool without passphrase
                    if any(s in str(e) for s in ('Wrong key', 'Missing -p flag')):
                        return False
        return True

    @private
    def geli_setkey(self, dev, key, slot=GELI_KEY_SLOT, passphrase=None, oldkey=None):
        cp = subprocess.run([
            'geli', 'setkey', '-n', str(slot),
        ] + (
            ['-J', passphrase] if passphrase else ['-P']
        ) + ['-K', key] + (
            ['-k', oldkey] if oldkey else []
        ) + [dev], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if cp.stderr:
            raise CallError(f'Unable to set passphrase on {dev}: {cp.stderr.decode()}')

        self.__geli_notify_passphrase(passphrase)

    @private
    def geli_delkey(self, dev, slot=GELI_KEY_SLOT, force=False):
        cp = subprocess.run([
            'geli', 'delkey', '-n', str(slot),
        ] + (
            ['-f'] if force else []
        ) + [dev], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if cp.stderr:
            raise CallError(f'Unable to delete key {slot} on {dev}: {cp.stderr.decode()}')

    @private
    def geli_recoverykey_rm(self, pool):
        for ed in self.middleware.call_sync(
            'datastore.query', 'storage.encrypteddisk', [('encrypted_volume', '=', pool['id'])]
        ):
            dev = ed['encrypted_provider']
            self.geli_delkey(dev, GELI_RECOVERY_SLOT, True)

    @private
    def geli_passphrase(self, pool, passphrase, rmrecovery=False):
        """
        Set a passphrase in a geli
        If passphrase is None then remove the passphrase
        """
        if passphrase:
            passf = tempfile.NamedTemporaryFile(mode='w+', dir='/tmp/')
            os.chmod(passf.name, 0o600)
            passf.write(passphrase)
            passf.flush()
            passphrase = passf.name
        try:
            for ed in self.middleware.call_sync(
                'datastore.query', 'storage.encrypteddisk', [('encrypted_volume', '=', pool['id'])]
            ):
                dev = ed['encrypted_provider']
                if rmrecovery:
                    self.geli_delkey(dev, GELI_RECOVERY_SLOT, force=True)
                self.geli_setkey(dev, pool['encryptkey_path'], GELI_KEY_SLOT, passphrase)
        finally:
            if passphrase:
                passf.close()

    @private
    def geli_rekey(self, pool, slot=GELI_KEY_SLOT):
        """
        Regenerates the geli global key and set it to devices
        Removes the passphrase if it was present
        """

        geli_keyfile = pool['encryptkey_path']
        geli_keyfile_tmp = f'{geli_keyfile}.tmp'
        devs = [
            ed['encrypted_provider']
            for ed in self.middleware.call_sync(
                'datastore.query', 'storage.encrypteddisk', [('encrypted_volume', '=', pool['id'])]
            )
        ]

        # keep track of which device has which key in case something goes wrong
        dev_to_keyfile = {dev: geli_keyfile for dev in devs}

        # Generate new key as .tmp
        self.logger.debug("Creating new key file: %s", geli_keyfile_tmp)
        self.middleware.call_sync('disk.create_keyfile', geli_keyfile_tmp, 64, True)
        error = None
        applied = []
        for dev in devs:
            try:
                self.geli_setkey(dev, geli_keyfile_tmp, slot)
                dev_to_keyfile[dev] = geli_keyfile_tmp
                applied.append(dev)
            except Exception as ee:
                error = str(ee)
                self.logger.error('Failed to set geli key on %s: %s', dev, error, exc_info=True)
                break

        # Try to be atomic in a certain way
        # If rekey failed for one of the devs, revert for the ones already applied
        if error:
            could_not_restore = False
            for dev in applied:
                try:
                    self.geli_setkey(dev, geli_keyfile, slot, oldkey=geli_keyfile_tmp)
                    dev_to_keyfile[dev] = geli_keyfile
                except Exception as ee:
                    # this is very bad for the user, at the very least there
                    # should be a notification that they will need to
                    # manually rekey as they now have drives with different keys
                    could_not_restore = True
                    self.logger.error(
                        'Failed to restore key on rekey for %s: %s', dev, str(ee), exc_info=True
                    )
            if could_not_restore:
                try:
                    open(GELI_REKEY_FAILED, 'w').close()
                except Exception:
                    pass
                self.logger.error(
                    'Unable to rekey. Devices now have the following keys: %s',
                    '\n'.join([
                        f'{dev}: {keyfile}'
                        for dev, keyfile in dev_to_keyfile
                    ])
                )
                raise CallError(
                    'Unable to rekey and devices have different keys. See the log file.'
                )
            else:
                raise CallError(f'Unable to set key: {error}')
        else:
            if os.path.exists(GELI_REKEY_FAILED):
                try:
                    os.unlink(GELI_REKEY_FAILED)
                except Exception:
                    pass
            self.logger.debug("Rename geli key %s -> %s", geli_keyfile_tmp, geli_keyfile)
            os.rename(geli_keyfile_tmp, geli_keyfile)

    @private
    def geli_recoverykey_add(self, pool):
        with tempfile.NamedTemporaryFile(dir='/tmp/') as reckey:
            reckey_file = reckey.name
            self.middleware.call_sync('disk.create_keyfile', reckey_file, 64, True)
            reckey.flush()

            errors = []

            for ed in self.middleware.call_sync(
                'datastore.query', 'storage.encrypteddisk', [('encrypted_volume', '=', pool['id'])]
            ):
                dev = ed['encrypted_provider']
                try:
                    self.geli_setkey(dev, reckey_file, GELI_RECOVERY_SLOT, None)
                except Exception as ee:
                    errors.append(str(ee))

            if errors:
                raise CallError(
                    'Unable to set recovery key for {len(errors)} devices: {", ".join(errors)}'
                )
            reckey.seek(0)
            return base64.b64encode(reckey.read()).decode()

    @private
    def geli_detach_single(self, dev):
        if not os.path.exists(f'/dev/{dev.replace(".eli", "")}.eli'):
            return
        cp = subprocess.run(
            ['geli', 'detach', dev], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if cp.returncode != 0:
            raise CallError(f'Unable to geli dettach {dev}: {cp.stderr.decode()}')

    @private
    def geli_clear(self, dev):
        cp = subprocess.run(
            ['geli', 'clear', dev], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if cp.returncode != 0:
            raise CallError(f'Unable to geli clear {dev}: {cp.stderr.decode()}')

    @private
    def geli_detach(self, pool, clear=False):
        failed = 0
        for ed in self.middleware.call_sync(
            'datastore.query', 'storage.encrypteddisk', [('encrypted_volume', '=', pool['id'])]
        ):
            dev = ed['encrypted_provider']
            try:
                self.geli_detach_single(dev)
            except Exception as ee:
                self.logger.warn(str(ee))
                failed += 1
            if clear:
                try:
                    self.geli_clear(dev)
                except Exception as e:
                    self.logger.warn('Failed to clear %s: %s', dev, e)
        return failed

    def __geli_notify_passphrase(self, passphrase):
        if passphrase:
            with open(passphrase) as f:
                self.middleware.call_hook_sync('disk.post_geli_passphrase', f.read())
        else:
            self.middleware.call_hook_sync('disk.post_geli_passphrase', None)

    @private
    async def get_reserved(self):
        reserved = list(await self.middleware.call('boot.get_disks'))
        reserved += [i async for i in await self.middleware.call('pool.get_disks')]
        reserved += [i async for i in self.__get_iscsi_targets()]
        return reserved

    async def __get_iscsi_targets(self):
        iscsi_target_extent_paths = [
            extent["iscsi_target_extent_path"]
            for extent in await self.middleware.call('datastore.query', 'services.iscsitargetextent',
                                                     [('iscsi_target_extent_type', '=', 'Disk')])
        ]
        for disk in await self.middleware.call('datastore.query', 'storage.disk',
                                               [('disk_identifier', 'in', iscsi_target_extent_paths)]):
            yield disk["disk_name"]

    async def __get_partitions(self, disk):
        partitions = []
        name = await self.middleware.call("disk.get_name", disk)
        for path in glob.glob(f"/dev/%s[a-fps]*" % name) or [f"/dev/{name}"]:
            cp = await run("/usr/sbin/diskinfo", path, check=False)
            if cp.returncode:
                self.logger.debug('Failed to get diskinfo for %s: %s', name, cp.stderr.decode())
                continue
            info = cp.stdout.decode("utf-8").split("\t")
            if len(info) > 3:
                partitions.append({
                    "path": path,
                    "capacity": int(info[2]),
                })

        return partitions

    @private
    def check_clean(self, disk):
        geom.scan()
        return geom.class_by_name('PART').xml.find(f'.//geom[name="{disk}"]') is None

    @private
    async def sed_unlock_all(self):
        advconfig = await self.middleware.call('system.advanced.config')
        disks = await self.middleware.call('disk.query', [], {'extra': {'passwords': True}})

        # If no SED password was found we can stop here
        if not await self.middleware.call('system.advanced.sed_global_password') and not any(
            [d['passwd'] for d in disks]
        ):
            return

        result = await asyncio_map(lambda disk: self.sed_unlock(disk['name'], disk, advconfig), disks, 16)
        locked = list(filter(lambda x: x['locked'] is True, result))
        if locked:
            disk_names = ', '.join([i['name'] for i in locked])
            self.logger.warn(f'Failed to unlock following SED disks: {disk_names}')
            raise CallError('Failed to unlock SED disks', errno.EACCES)
        return True

    @private
    async def sed_unlock(self, disk_name, disk=None, _advconfig=None):
        if _advconfig is None:
            _advconfig = await self.middleware.call('system.advanced.config')

        devname = f'/dev/{disk_name}'
        # We need two states to tell apart when disk was successfully unlocked
        locked = None
        unlocked = None
        password = await self.middleware.call('system.advanced.sed_global_password')

        if disk is None:
            disk = await self.query([('name', '=', disk_name)], {'extra': {'passwords': True}})
            if disk and disk[0]['passwd']:
                password = disk[0]['passwd']
        elif disk.get('passwd'):
            password = disk['passwd']

        rv = {'name': disk_name, 'locked': None}

        if not password:
            # If there is no password no point in continuing
            return rv

        # Try unlocking TCG OPAL using sedutil
        cp = await run('sedutil-cli', '--query', devname, check=False)
        if cp.returncode == 0:
            output = cp.stdout.decode(errors='ignore')
            if 'Locked = Y' in output:
                locked = True
                cp = await run('sedutil-cli', '--setLockingRange', '0', 'RW', password, devname, check=False)
                if cp.returncode == 0:
                    locked = False
                    unlocked = True
            elif 'Locked = N' in output:
                locked = False

        # Try ATA Security if SED was not unlocked and its not locked by OPAL
        if not unlocked and not locked:
            cp = await run('camcontrol', 'security', devname, check=False)
            if cp.returncode == 0:
                output = cp.stdout.decode()
                if RE_CAMCONTROL_DRIVE_LOCKED.search(output):
                    locked = True
                    cp = await run(
                        'camcontrol', 'security', devname,
                        '-U', _advconfig['sed_user'],
                        '-k', password,
                        check=False,
                    )
                    if cp.returncode == 0:
                        locked = False
                        unlocked = True
                else:
                    locked = False

        if unlocked:
            try:
                # Disk needs to be retasted after unlock
                with open(devname, 'wb'):
                    pass
            except OSError:
                pass
        elif locked:
            self.logger.error(f'Failed to unlock {disk_name}')
        rv['locked'] = locked
        return rv

    @private
    async def sed_initial_setup(self, disk_name, password):
        """
        NO_SED - Does not support SED
        ACCESS_GRANTED - Already setup and `password` is a valid password
        LOCKING_DISABLED - Locking range is disabled
        SETUP_FAILED - Initial setup call failed
        SUCCESS - Setup successfully completed
        """
        devname = f'/dev/{disk_name}'

        cp = await run('sedutil-cli', '--isValidSED', devname, check=False)
        if b' SED ' not in cp.stdout:
            return 'NO_SED'

        cp = await run('sedutil-cli', '--listLockingRange', '0', password, devname, check=False)
        if cp.returncode == 0:
            output = cp.stdout.decode()
            if RE_SED_RDLOCK_EN.search(output) and RE_SED_WRLOCK_EN.search(output):
                return 'ACCESS_GRANTED'
            else:
                return 'LOCKING_DISABLED'

        try:
            await run('sedutil-cli', '--initialSetup', password, devname)
        except subprocess.CalledProcessError as e:
            self.logger.debug(f'initialSetup failed for {disk_name}:\n{e.stdout}{e.stderr}')
            return 'SETUP_FAILED'

        # OPAL 2.0 disks do not enable locking range on setup like Enterprise does
        try:
            await run('sedutil-cli', '--enableLockingRange', '0', password, devname)
        except subprocess.CalledProcessError as e:
            self.logger.debug(f'enableLockingRange failed for {disk_name}:\n{e.stdout}{e.stderr}')
            return 'SETUP_FAILED'

        return 'SUCCESS'

    async def __multipath_create(self, name, consumers, mode=None):
        """
        Create an Active/Passive GEOM_MULTIPATH provider
        with name ``name`` using ``consumers`` as the consumers for it

        Modes:
            A - Active/Active
            R - Active/Read
            None - Active/Passive

        Returns:
            True in case the label succeeded and False otherwise
        """
        cmd = ["/sbin/gmultipath", "label", name] + consumers
        if mode:
            cmd.insert(2, f'-{mode}')
        p1 = await Popen(cmd, stdout=subprocess.PIPE)
        if (await p1.wait()) != 0:
            return False
        return True

    async def __multipath_next(self):
        """
        Find out the next available name for a multipath named diskX
        where X is a crescenting value starting from 1

        Returns:
            The string of the multipath name to be created
        """
        await self.middleware.run_in_thread(geom.scan)
        numbers = sorted([
            int(RE_MPATH_NAME.search(g.name).group(1))
            for g in geom.class_by_name('MULTIPATH').geoms if RE_MPATH_NAME.match(g.name)
        ])
        if not numbers:
            numbers = [0]
        for number in range(1, numbers[-1] + 2):
            if number not in numbers:
                break
        else:
            raise ValueError('Could not find multipaths')
        return f'disk{number}'

    @private
    @accepts()
    async def multipath_sync(self):
        """
        Synchronize multipath disks

        Every distinct GEOM_DISK that shares an ident (aka disk serial)
        with conjunction of the lunid is considered a multipath and will be
        handled by GEOM_MULTIPATH.

        If the disk is not currently in use by some Volume or iSCSI Disk Extent
        then a gmultipath is automatically created and will be available for use.
        """

        await self.middleware.run_in_thread(geom.scan)

        mp_disks = []
        for g in geom.class_by_name('MULTIPATH').geoms:
            for c in g.consumers:
                p_geom = c.provider.geom
                # For now just DISK is allowed
                if p_geom.clazz.name != 'DISK':
                    self.logger.warn(
                        "A consumer that is not a disk (%s) is part of a "
                        "MULTIPATH, currently unsupported by middleware",
                        p_geom.clazz.name
                    )
                    continue
                mp_disks.append(p_geom.name)

        reserved = await self.get_reserved()

        is_freenas = await self.middleware.call('system.is_freenas')

        serials = defaultdict(list)
        active_active = []
        for g in geom.class_by_name('DISK').geoms:
            if not RE_DA.match(g.name) or g.name in reserved or g.name in mp_disks:
                continue
            if not is_freenas:
                descr = g.provider.config.get('descr') or ''
                if (
                    descr == 'STEC ZeusRAM' or
                    descr.startswith('VIOLIN') or
                    descr.startswith('3PAR')
                ):
                    active_active.append(g.name)
            serial = ''
            v = g.provider.config.get('ident')
            if v:
                serial = v
            v = g.provider.config.get('lunid')
            if v:
                serial += v
            if not serial:
                continue
            size = g.provider.mediasize
            serials[(serial, size)].append(g.name)
            serials[(serial, size)].sort(key=lambda x: int(x[2:]))

        disks_pairs = [disks for disks in list(serials.values())]
        disks_pairs.sort(key=lambda x: int(x[0][2:]))

        # Mode is Active/Passive for FreeNAS
        mode = None if is_freenas else 'R'
        for disks in disks_pairs:
            if not len(disks) > 1:
                continue
            name = await self.__multipath_next()
            await self.__multipath_create(name, disks, 'A' if disks[0] in active_active else mode)

        # Scan again to take new multipaths into account
        await self.middleware.run_in_thread(geom.scan)
        mp_ids = []
        for g in geom.class_by_name('MULTIPATH').geoms:
            _disks = []
            for c in g.consumers:
                p_geom = c.provider.geom
                # For now just DISK is allowed
                if p_geom.clazz.name != 'DISK':
                    continue
                _disks.append(p_geom.name)

            qs = await self.middleware.call('datastore.query', 'storage.disk', [
                ['OR', [
                    ['disk_name', 'in', _disks],
                    ['disk_multipath_member', 'in', _disks],
                ]],
            ])
            if qs:
                diskobj = qs[0]
                mp_ids.append(diskobj['disk_identifier'])
                update = False  # Make sure to not update if nothing changed
                if diskobj['disk_multipath_name'] != g.name:
                    update = True
                    diskobj['disk_multipath_name'] = g.name
                if diskobj['disk_name'] in _disks:
                    _disks.remove(diskobj['disk_name'])
                if _disks and diskobj['disk_multipath_member'] != _disks[-1]:
                    update = True
                    diskobj['disk_multipath_member'] = _disks.pop()
                if update:
                    await self.middleware.call('datastore.update', 'storage.disk', diskobj['disk_identifier'], diskobj)

        # Update all disks which were not identified as MULTIPATH, resetting attributes
        for disk in (await self.middleware.call('datastore.query', 'storage.disk', [('disk_identifier', 'nin', mp_ids)])):
            if disk['disk_multipath_name'] or disk['disk_multipath_member']:
                disk['disk_multipath_name'] = ''
                disk['disk_multipath_member'] = ''
                await self.middleware.call('datastore.update', 'storage.disk', disk['disk_identifier'], disk)

    @private
    async def label(self, dev, label):
        cp = await run('geom', 'label', 'label', label, dev, check=False)
        if cp.returncode != 0:
            raise CallError(f'Failed to label {dev}: {cp.stderr.decode()}')

    @private
    async def configure_power_management(self):
        """
        This runs on boot to properly configure all power management options
        (Advanced Power Management, Automatic Acoustic Management and IDLE) for all disks.
        """
        # Only run power management for FreeNAS
        if not await self.middleware.call('system.is_freenas'):
            return
        for disk in await self.middleware.call('disk.query'):
            await self.power_management(disk['name'], disk=disk)

    @private
    async def power_management(self, dev, disk=None):
        """
        Actually sets power management for `dev`.
        `disk` is the disk.query entry and optional so this can be called only with disk name.
        """
        if not disk:
            disk = await self.middleware.call('disk.query', [('name', '=', dev)])
            if not disk:
                return
            disk = disk[0]

        try:
            identify = (await run('camcontrol', 'identify', dev)).stdout.decode()
        except subprocess.CalledProcessError:
            return

        # Try to set APM
        if RE_CAMCONTROL_APM.search(identify):
            args = ['camcontrol', 'apm', dev]
            if disk['advpowermgmt'] != 'DISABLED':
                args += ['-l', disk['advpowermgmt']]
            asyncio.ensure_future(run(*args, check=False))

        # Try to set AAM
        if RE_CAMCONTROL_AAM.search(identify):
            acousticlevel_map = {
                'MINIMUM': '1',
                'MEDIUM': '64',
                'MAXIMUM': '127',
            }
            asyncio.ensure_future(run(
                'camcontrol', 'aam', dev, '-l', acousticlevel_map.get(disk['acousticlevel'], '0'),
                check=False,
            ))

        # Try to set idle
        if RE_CAMCONTROL_POWER.search(identify):
            if disk['hddstandby'] != 'ALWAYS ON':
                # database is in minutes, camcontrol uses seconds
                idle = int(disk['hddstandby']) * 60
            else:
                idle = 0

            # We wait a minute before applying idle because its likely happening during system boot
            # or some activity is happening very soon.
            async def camcontrol_idle():
                await asyncio.sleep(60)
                asyncio.ensure_future(run('camcontrol', 'idle', dev, '-t', str(idle), check=False))

            asyncio.ensure_future(camcontrol_idle())


async def devd_devfs_hook(middleware, data):
    if data.get('subsystem') != 'CDEV':
        return

    if data['type'] == 'CREATE':
        disks = await middleware.run_in_thread(lambda: sysctl.filter('kern.disks')[0].value.split())
        # Device notified about is not a disk
        if data['cdev'] not in disks:
            return
        await middleware.call('disk.sync', data['cdev'])
        await middleware.call('disk.sed_unlock', data['cdev'])
        await middleware.call('disk.multipath_sync')
        await middleware.call('alert.oneshot_delete', 'SMART', data['cdev'])
    elif data['type'] == 'DESTROY':
        # Device notified about is not a disk
        if not RE_ISDISK.match(data['cdev']):
            return
        await (await middleware.call('disk.sync_all')).wait()
        await middleware.call('disk.multipath_sync')
        await middleware.call('alert.oneshot_delete', 'SMART', data['cdev'])
        # If a disk dies we need to reconfigure swaps so we are not left
        # with a single disk mirror swap, which may be a point of failure.
        await middleware.call('disk.swaps_configure')


async def devd_zfs_hook(middleware, data):
    # Swap must be configured only on disks being used by some pool,
    # for this reason we must react to certain types of ZFS events to keep
    # it in sync every time there is a change.
    if data.get('type') in (
        'misc.fs.zfs.config_sync',
        'misc.fs.zfs.pool_create',
        'misc.fs.zfs.pool_destroy',
        'misc.fs.zfs.pool_import',
    ):
        asyncio.ensure_future(middleware.call('disk.swaps_configure'))


async def _event_system_ready(middleware, event_type, args):
    if args['id'] != 'ready':
        return

    # Configure disks power management
    asyncio.ensure_future(middleware.call('disk.configure_power_management'))


def setup(middleware):
    # Listen to DEVFS events so we can sync on disk attach/detach
    middleware.register_hook('devd.devfs', devd_devfs_hook)
    # Listen to ZFS events to reconfigure swap on pool create/export/import
    middleware.register_hook('devd.zfs', devd_zfs_hook)
    # Run disk tasks once system is ready (e.g. power management)
    middleware.event_subscribe('system', _event_system_ready)
