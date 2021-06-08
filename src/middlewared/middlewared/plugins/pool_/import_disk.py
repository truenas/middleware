import asyncio
import async_timeout
import os
import logging
import re
import subprocess

from middlewared.job import JobProgressBuffer
from middlewared.schema import Dict, returns, Str
from middlewared.service import accepts, CallError, job, Service
from middlewared.utils import Popen

logger = logging.getLogger(__name__)


class PoolService(Service):

    @accepts(
        Str('device'),
        Str('fs_type'),
        Dict('fs_options', additional_attrs=True),
        Str('dst_path')
    )
    @returns()
    @job(lock=lambda args: 'volume_import', logs=True, abortable=True)
    async def import_disk(self, job, device, fs_type, fs_options, dst_path):
        """
        Import a disk, by copying its content to a pool.

        .. examples(websocket)::

          Import a FAT32 (msdosfs) disk.

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.import_disk,
                "params": [
                    "/dev/da0", "msdosfs", {}, "/mnt/tank/mydisk"
                ]
            }
        """
        job.set_progress(None, description='Mounting')

        src = os.path.join('/var/run/importcopy/tmpdir', os.path.relpath(device, '/'))

        if os.path.exists(src):
            os.rmdir(src)

        try:
            os.makedirs(src)

            async with await self.middleware.call('pool.import_disk_kernel_module_context_manager', fs_type):
                async with await self.middleware.call('pool.import_disk_mount_fs_context_manager', device, src,
                                                      fs_type, fs_options):
                    job.set_progress(None, description='Importing')

                    line = [
                        'rsync',
                        '--info=progress2',
                        '--modify-window=1',
                        '-rltvh',
                        '--no-perms',
                        src + '/',
                        dst_path
                    ]
                    rsync_proc = await Popen(
                        line, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0, preexec_fn=os.setsid,
                    )
                    try:
                        progress_buffer = JobProgressBuffer(job)
                        while True:
                            line = await rsync_proc.stdout.readline()
                            job.logs_fd.write(line)
                            if line:
                                try:
                                    line = line.decode('utf-8', 'ignore').strip()
                                    bits = re.split(r'\s+', line)
                                    if len(bits) == 6 and bits[1].endswith('%') and bits[1][:-1].isdigit():
                                        progress_buffer.set_progress(int(bits[1][:-1]))
                                    elif not line.endswith('/'):
                                        if (
                                            line not in ['sending incremental file list'] and
                                            'xfr#' not in line
                                        ):
                                            progress_buffer.set_progress(None, extra=line)
                                except Exception:
                                    logger.warning('Parsing error in rsync task', exc_info=True)
                            else:
                                break

                        progress_buffer.flush()
                        await rsync_proc.wait()
                        if rsync_proc.returncode != 0:
                            raise Exception('rsync failed with exit code %r' % rsync_proc.returncode)
                    finally:
                        if rsync_proc.returncode is None:
                            try:
                                logger.warning("Terminating rsync")
                                rsync_proc.terminate()
                                try:
                                    async with async_timeout.timeout(10):
                                        await rsync_proc.wait()
                                except asyncio.TimeoutError:
                                    logger.warning("Timeout waiting for rsync to terminate, killing it")
                                    rsync_proc.kill()
                                    await asyncio.sleep(5)  # For children to die before unmount
                            except ProcessLookupError:
                                logger.warning("rsync process lookup error")

                    job.set_progress(100, description='Done', extra='')
        finally:
            os.rmdir(src)

    @accepts(Str("device"))
    @returns(Str('filesystem', null=True))
    def import_disk_autodetect_fs_type(self, device):
        """
        Autodetect filesystem type for `pool.import_disk`.

        .. examples(websocket)::

            :::javascript
            {
                "id": "6841f242-840a-11e6-a437-00e04d680384",
                "msg": "method",
                "method": "pool.import_disk_autodetect_fs_type",
                "params": ["/dev/da0"]
            }
        """
        proc = subprocess.Popen(["blkid", device], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="utf-8")
        output = proc.communicate()[0].strip()

        if proc.returncode == 2:
            proc = subprocess.Popen(["file", "-s", device], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    encoding="utf-8")
            output = proc.communicate()[0].strip()
            if proc.returncode != 0:
                raise CallError(f"blkid failed with code 2 and file failed with code {proc.returncode}: {output}")

            if "Unix Fast File system" in output:
                return "ufs"

            raise CallError(f"blkid failed with code 2 and file produced unexpected output: {output}")

        if proc.returncode != 0:
            raise CallError(f"blkid failed with code {proc.returncode}: {output}")

        m = re.search("TYPE=\"(.+?)\"", output)
        if m is None:
            raise CallError(f"blkid produced unexpected output: {output}")

        fs = {
            "ext2": "ext2fs",
            "ext3": "ext2fs",
            "ntfs": "ntfs",
            "vfat": "msdosfs",
        }.get(m.group(1))
        if fs is None:
            self.logger.info("Unknown FS: %s", m.group(1))
            return None

        return fs
