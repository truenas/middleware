import tempfile
import tarfile
import shutil

from middlewared.service import Service, job, CallError
from .utils import GlusterConfig


class GlusterBackupService(Service):
    arcname = 'gluster_config'

    class Config:
        namespace = 'gluster.backup'
        private = True

    @job(pipes=['output'])
    def save(self, job):
        with tempfile.NamedTemporaryFile(delete=True) as tf:
            with tarfile.open(tf.name, 'w') as tar:
                tar.add(GlusterConfig.WORKDIR.value, arcname=self.arcname)

            with open(tf.name, 'rb') as f:
                shutil.copyfileobj(f, job.pipes.output.w)

    @job(pipes=['input'])
    def upload(self, job):
        # stop service and clean out any existing config
        self.middleware.call_sync('service.stop', 'glusterd')
        shutil.rmtree(GlusterConfig.WORKDIR.value)

        # save the archive file provided to us to a temp file
        chunk = 1024
        max_size = chunk * 10  # only keep 10MB in memory
        with tempfile.SpooledTemporaryFile(max_size=max_size) as stf:
            with open(stf.name, 'wb') as f:
                while True:
                    read = job.pipes.input.r.read(chunk)
                    if read == b'':
                        break
                    else:
                        f.write(read)

            # let's check to make sure this is a tar file
            if not tarfile.is_tarfile(stf.name):
                raise CallError('Expecting a tarfile')

            # extract the the archive
            with tarfile.open(stf.name, 'rb') as tar:
                expected = f.next()
                if not expected or expected.name != self.arcname:
                    raise CallError('Invalid tar archive')

                tar.extractall(path=GlusterConfig.WORKDIR.value)

            # copies everything from /var/db/system/glusterd/gluster_config up 1 dir
            # (i.e. copies it to /var/db/system/glusterd)
            src = f'{GlusterConfig.WORKDIR.value}/{self.arcname}'
            dst = GlusterConfig.WORKDIR.value
            shutil.copytree(src, dst, dirs_exist_ok=True)

        # now clean up
        shutil.rmtree(src, ignore_errors=True)
        self.middleware.call_sync('service.start', 'glusterd')
