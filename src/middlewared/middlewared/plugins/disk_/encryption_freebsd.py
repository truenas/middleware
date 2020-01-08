import os
import subprocess
import tempfile

from middlewared.service import CallError, private, Service
from middlewared.utils import run

from .encryption_base import DiskEncryptionBase


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

    async def remove_encryption(self, device):
        cp = await run('geli', 'detach', device, check=False, encoding='utf8')
        if cp.returncode:
            raise CallError(f'Failed to detach geli from {device}: {cp.stderr}')
