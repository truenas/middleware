import os
import subprocess
import tempfile

from middlewared.service import CallError, private, Service
from middlewared.utils import run

from .encryption_base import DiskEncryptionBase

GELI_KEY_SLOT = 0
GELI_RECOVERY_SLOT = 1


class DiskService(Service, DiskEncryptionBase):
    def decrypt(self, job, devices, passphrase=None):
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
                ['geli', 'attach',] + (['-j', passphrase] if passphrase else ['-p']) + ['-k', key, dev,],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            if cp.stderr or not os.path.exists(f'/dev/{dev}.eli'):
                raise CallError(f'Unable to geli attach {dev}: {cp.stderr.decode()}')
            self.__geli_notify_passphrase(passphrase)
        else:
            self.logger.debug(f'{dev} already attached')

    def __geli_notify_passphrase(self, passphrase):
        if passphrase:
            with open(passphrase) as f:
                self.middleware.call_hook_sync('disk.post_geli_passphrase', f.read())
        else:
            self.middleware.call_hook_sync('disk.post_geli_passphrase', None)

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

        self.__geli_notify_passphrase(passphrase)

    @private
    def geli_delkey(self, dev, slot=GELI_KEY_SLOT, force=False):
        cp = subprocess.run(
            ['geli', 'delkey', '-n', str(slot)] + (['-f'] if force else []) + [dev],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        if cp.stderr:
            raise CallError(f'Unable to delete key {slot} on {dev}: {cp.stderr.decode()}')

    async def remove_encryption(self, device):
        cp = await run('geli', 'detach', device, check=False, encoding='utf8')
        if cp.returncode:
            raise CallError(f'Failed to detach geli from {device}: {cp.stderr}')
