import base64
import os
import subprocess
import tempfile

from bsd import geom

from middlewared.schema import accepts, Bool, Dict
from middlewared.service import CallError, private, Service
from middlewared.utils import run

from .encryption_base import DiskEncryptionBase

GELI_KEY_SLOT = 0
GELI_RECOVERY_SLOT = 1
GELI_REKEY_FAILED = '/tmp/.rekey_failed'


class DiskService(Service, DiskEncryptionBase):
    def decrypt(self, job, devices, passphrase):
        with tempfile.NamedTemporaryFile(dir='/tmp/') as f:
            os.chmod(f.name, 0o600)
            f.write(job.pipes.input.r.read())
            f.flush()

            if passphrase:
                passf = tempfile.NamedTemporaryFile(mode='w+', dir='/tmp/')
                os.chmod(passf.name, 0o600)
                passf.write(passphrase)
                passf.flush()
                passphrase = passf.name

            failed = []
            for dev in devices:
                try:
                    self.middleware.call_sync(
                        'disk.geli_attach_single',
                        dev,
                        f.name,
                        passphrase,
                    )
                except Exception:
                    failed.append(dev)

            if passphrase:
                passf.close()

            if failed:
                raise CallError(f'The following devices failed to attach: {", ".join(failed)}')

        return True

    @private
    def encrypt(self, devname, keypath, passphrase_path=None):
        self.__geli_setmetadata(devname, keypath, passphrase_path)
        self.geli_attach_single(devname, keypath, passphrase_path)
        return f'{devname}.eli'

    def __geli_setmetadata(self, dev, keyfile, passphrase_path=None):
        self.create_keyfile(keyfile)
        cp = subprocess.run([
            'geli', 'init', '-s', '4096', '-l', '256', '-B', 'none',
        ] + (
            ['-J', passphrase_path] if passphrase_path else ['-P']
        ) + ['-K', keyfile, dev], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if cp.stderr:
            raise CallError(f'Unable to set geli metadata on {dev}: {cp.stderr.decode()}')

    @private
    def geli_attach_single(self, dev, key, passphrase=None, skip_existing=False):
        if skip_existing or not os.path.exists(f'/dev/{dev}.eli'):
            cp = subprocess.run(
                ['geli', 'attach'] + (['-j', passphrase] if passphrase else ['-p']) + ['-k', key, dev],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            if cp.stderr or not os.path.exists(f'/dev/{dev}.eli'):
                raise CallError(f'Unable to geli attach {dev}: {cp.stderr.decode()}')
        else:
            self.logger.debug(f'{dev} already attached')

    @private
    def create_keyfile(self, keyfile, size=64, force=False):
        if force or not os.path.exists(keyfile):
            keypath = os.path.dirname(keyfile)
            if not os.path.exists(keypath):
                os.makedirs(keypath)
            subprocess.run(
                ['dd', 'if=/dev/random', f'of={keyfile}', f'bs={size}', 'count=1'],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

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
        self.logger.debug('Creating new key file: %s', geli_keyfile_tmp)
        self.middleware.call_sync('disk.create_keyfile', geli_keyfile_tmp, 64, True)
        error = None
        applied = []
        for dev in devs:
            try:
                self.middleware.call_sync('disk.geli_setkey', dev, geli_keyfile_tmp, slot)
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
                    self.middleware.call_sync('disk.geli_setkey', dev, geli_keyfile, slot, None, geli_keyfile_tmp)
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
                        f'{dev}: {keyfile}' for dev, keyfile in dev_to_keyfile
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
    def geli_setkey(self, dev, key, slot=GELI_KEY_SLOT, passphrase=None, oldkey=None):
        cp = subprocess.run(
            ['geli', 'setkey', '-n', str(slot)] + (
                ['-J', passphrase] if passphrase else ['-P']
            ) + ['-K', key] + (['-k', oldkey] if oldkey else []) + [dev],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        if cp.stderr:
            raise CallError(f'Unable to set passphrase on {dev}: {cp.stderr.decode()}')

    @private
    def geli_delkey(self, dev, slot=GELI_KEY_SLOT, force=False):
        cp = subprocess.run(
            ['geli', 'delkey', '-n', str(slot)] + (['-f'] if force else []) + [dev],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        if cp.stderr:
            raise CallError(f'Unable to delete key {slot} on {dev}: {cp.stderr.decode()}')

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

    async def remove_encryption(self, device):
        cp = await run('geli', 'detach', device, check=False, encoding='utf8')
        if cp.returncode:
            raise CallError(f'Failed to detach geli from {device}: {cp.stderr}')

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
    def geli_recoverykey_rm(self, pool):
        for ed in self.middleware.call_sync(
                'datastore.query', 'storage.encrypteddisk', [('encrypted_volume', '=', pool['id'])]
        ):
            dev = ed['encrypted_provider']
            self.middleware.call_sync('disk.geli_delkey', dev, GELI_RECOVERY_SLOT, True)

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
                    self.middleware.call_sync('disk.geli_setkey', dev, reckey_file, GELI_RECOVERY_SLOT)
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
            raise CallError(f'Unable to geli detach {dev}: {cp.stderr.decode()}')

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

    @accepts(Dict(
        'options',
        Bool('unused', default=False),
    ))
    def get_encrypted(self, options):
        """
        Get all geli providers

        It might be an entire disk or a partition of type freebsd-zfs.

        Before a geli encrypted pool can be imported, disks used in the pool should be decrypted
        and then pool import can proceed as desired. In that case `unused` can be passed as `true`, to find out
        which disks are geli encrypted but not being used by active ZFS pools.
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
                if p.config is None:
                    continue

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
