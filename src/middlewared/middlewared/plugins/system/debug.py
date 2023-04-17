import io
import os
import requests
import shutil
import tarfile

from middlewared.schema import accepts, returns
from middlewared.service import CallError, job, private, Service

from ixdiagnose.config import conf
from ixdiagnose.event import event_callbacks
from ixdiagnose.run import generate_debug

from .utils import DEBUG_MAX_SIZE


class SystemService(Service):

    @private
    @job(lock='system.debug_generate')
    def debug_generate(self, job):
        """
        Generate system debug file.

        Result value will be the absolute path of the file.
        """
        system_dataset_path = self.middleware.call_sync('systemdataset.config')['path']
        if system_dataset_path is not None:
            direc = os.path.join(system_dataset_path, 'ixdiagnose')
        else:
            direc = '/var/tmp/ixdiagnose'
        dump = os.path.join(direc, 'ixdiagnose.tgz')

        # Be extra safe in case we have left over from previous run
        if os.path.exists(direc):
            shutil.rmtree(direc)

        conf.apply({
            'compress': True,
            'debug_path': os.path.join(direc, 'debug'),
            'clean_debug_path': True,
            'compressed_path': dump,
        })

        def progress_callback(percent, desc):
            job.set_progress(percent, desc)

        event_callbacks.register(progress_callback)

        try:
            return generate_debug()
        except Exception as e:
            raise CallError(f'Failed to generate debug: {e!r}')

    @accepts()
    @returns()
    @job(lock='system.debug', pipes=['output'])
    def debug(self, job):
        """
        Download a debug file.
        """
        job.set_progress(0, 'Generating debug file')
        debug_job = self.middleware.call_sync(
            'system.debug_generate',
            job_on_progress_cb=lambda encoded: job.set_progress(int(encoded['progress']['percent'] * 0.9),
                                                                encoded['progress']['description'])
        )

        standby_debug = None
        if self.middleware.call_sync('failover.licensed'):
            try:
                standby_debug = self.middleware.call_sync(
                    'failover.call_remote', 'system.debug_generate', [], {'job': True}
                )
            except Exception:
                self.logger.warn('Failed to get debug from standby node', exc_info=True)
            else:
                remote_ip = self.middleware.call_sync('failover.remote_ip')
                url = self.middleware.call_sync(
                    'failover.call_remote', 'core.download', ['filesystem.get', [standby_debug], 'debug.txz'],
                )[1]

                url = f'http://{remote_ip}:6000{url}'
                # no reason to honor proxy settings in this
                # method since we're downloading the debug
                # archive directly across the heartbeat
                # interface which is point-to-point
                proxies = {'http': '', 'https': ''}
                standby_debug = io.BytesIO()
                with requests.get(url, stream=True, proxies=proxies) as r:
                    for i in r.iter_content(chunk_size=1048576):
                        if standby_debug.tell() > DEBUG_MAX_SIZE * 1048576:
                            raise CallError(f'Standby debug file is bigger than {DEBUG_MAX_SIZE}MiB.')
                        standby_debug.write(i)

        debug_job.wait_sync()
        if debug_job.error:
            raise CallError(debug_job.error)

        job.set_progress(90, 'Preparing debug file for streaming')

        if standby_debug:
            # Debug file cannot be big on HA because we put both debugs in memory
            # so they can be downloaded at once.
            try:
                if os.stat(debug_job.result).st_size > DEBUG_MAX_SIZE * 1048576:
                    raise CallError(f'Debug file is bigger than {DEBUG_MAX_SIZE}MiB.')
            except FileNotFoundError:
                raise CallError('Debug file was not found, try again.')

            network = self.middleware.call_sync('network.configuration.config')
            node = self.middleware.call_sync('failover.node')

            tario = io.BytesIO()
            with tarfile.open(fileobj=tario, mode='w') as tar:

                if node == 'A':
                    my_hostname = network['hostname']
                    remote_hostname = network['hostname_b']
                else:
                    my_hostname = network['hostname_b']
                    remote_hostname = network['hostname']

                tar.add(debug_job.result, f'{my_hostname}.txz')

                tarinfo = tarfile.TarInfo(f'{remote_hostname}.txz')
                tarinfo.size = standby_debug.tell()
                standby_debug.seek(0)
                tar.addfile(tarinfo, fileobj=standby_debug)

            tario.seek(0)
            shutil.copyfileobj(tario, job.pipes.output.w)
        else:
            with open(debug_job.result, 'rb') as f:
                shutil.copyfileobj(f, job.pipes.output.w)
        job.pipes.output.w.close()
