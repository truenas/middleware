import os
import subprocess

from middlewared.service import job, private, Service


class CertificateService(Service):

    class Config:
        cli_namespace = 'system.certificate'

    @private
    async def dhparam(self):
        return '/data/dhparam.pem'

    @private
    @job()
    def dhparam_setup(self, job):
        dhparam_path = self.middleware.call_sync('certificate.dhparam')
        if not os.path.exists(dhparam_path) or os.stat(dhparam_path).st_size == 0:
            with open('/dev/console', 'wb') as console:
                with open(dhparam_path, 'wb') as f:
                    subprocess.run(
                        ['openssl', 'dhparam', '-rand', '/dev/urandom', '2048'], stdout=f, stderr=console, check=True
                    )
