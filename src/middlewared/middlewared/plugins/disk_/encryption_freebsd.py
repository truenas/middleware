import os
import tempfile

from middlewared.service import CallError, Service

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
