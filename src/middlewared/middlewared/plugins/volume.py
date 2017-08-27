import asyncio
import logging
import os
import re
import subprocess
import time

from middlewared.schema import accepts, Str
from middlewared.service import Service, job
from middlewared.utils import Popen, run

logger = logging.getLogger(__name__)

RE_MOUNT = re.compile(
    r'^(?P<fs_spec>.+?) on (?P<fs_file>.+?) \((?P<fs_vfstype>\w+)', re.S
)


async def get_mounted_filesystems():
    """Return a list of dict with info of mounted file systems

    Each dict is composed of:
        - fs_spec (src)
        - fs_file (dest)
        - fs_vfstype
    """
    mounted = []

    lines = (await run('/sbin/mount')).stdout.decode("utf8").splitlines()

    for line in lines:
        reg = RE_MOUNT.search(line)
        if not reg:
            continue
        mounted.append(reg.groupdict())

    return mounted


async def is_mounted(**kwargs):
    mounted = await get_mounted_filesystems()
    for mountpt in mounted:
        ret = False
        if 'device' in kwargs:
            ret = True if mountpt['fs_spec'] == kwargs['device'] else False
        if 'path' in kwargs:
            ret = True if mountpt['fs_file'] == kwargs['path'] else False
        if ret:
            break

    return ret


async def mount(dev, path, mntopts=None, fstype=None):
    mount_cmd = ['/sbin/mount']

    if isinstance(dev, str):
        dev = dev.encode('utf-8')

    if isinstance(path, str):
        path = path.encode('utf-8')

    if mntopts:
        opts = ['-o', mntopts]
    else:
        opts = []

    if fstype == 'ntfs':
        mount_cmd = ['/usr/local/bin/ntfs-3g']
        fstype = []
    else:
        fstype = ['-t', fstype] if fstype else []

    proc = await Popen(
        mount_cmd + opts + fstype + [dev, path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding='utf8',
    )
    output = await proc.communicate()

    if proc.returncode != 0:
        logger.debug("Mount failed (%s): %s", proc.returncode, output)
        raise ValueError("Mount failed {0} -> {1}, {2}" .format(
            proc.returncode,
            output[0],
            output[1]
        ))
    else:
        return True


async def umount(path, force=False):
    if force:
        cmdlst = ['/sbin/umount', '-f', path]
    else:
        cmdlst = ['/sbin/umount', path]

    proc = await Popen(
        cmdlst,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding='utf8',
    )
    output = await proc.communicate()

    if proc.returncode != 0:
        logger.debug("Umount failed (%s): %s", proc.returncode, output)
        raise ValueError("Unmount Failed {0} -> {1} {2}".format(
            proc.returncode,
            output[0],
            output[1]
        ))
    else:
        return True


class KernelModuleContextManager:
    def __init__(self, module):
        self.module = module

    async def __aenter__(self):
        if self.module is not None:
            if not await self.module_loaded():
                await run('kldload', self.module, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if not await self.module_loaded():
                    raise Exception('Kernel module %r failed to load', self.module)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.module is not None:
            try:
                await run('kldunload', self.module, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

    async def module_loaded(self):
        return (await run('kldstat', '-n', self.module, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)).returncode == 0


class MountFsContextManager:
    def __init__(self, dev, path, *args):
        self.dev = dev
        self.path = path
        self.args = args

    async def __aenter__(self):
        await mount(self.dev, self.path, *self.args)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if await is_mounted(device=self.dev, path=self.path):
            await umount(self.path)


class JobProgressBuffer:
    """
    This wrapper for `job.set_progress` strips too frequent progress updated
    (more frequent than `interval` seconds) so they don't spam websocket
    connections.
    """

    def __init__(self, job, interval=1):
        self.job = job

        self.interval = interval

        self.last_update_at = 0

        self.pending_update_body = None
        self.pending_update = None

    def set_progress(self, *args, **kwargs):
        t = time.monotonic()

        if t - self.last_update_at >= self.interval:
            if self.pending_update is not None:
                self.pending_update.cancel()

                self.pending_update_body = None
                self.pending_update = None

            self.last_update_at = t
            self.job.set_progress(*args, **kwargs)
        else:
            self.pending_update_body = args, kwargs

            if self.pending_update is None:
                self.pending_update = asyncio.get_event_loop().call_later(self.interval, self._do_pending_update)

    def cancel(self):
        if self.pending_update is not None:
            self.pending_update.cancel()

            self.pending_update_body = None
            self.pending_update = None

    def flush(self):
        if self.pending_update is not None:
            self.pending_update.cancel()

            self._do_pending_update()

    def _do_pending_update(self):
        self.last_update_at = time.monotonic()
        self.job.set_progress(*self.pending_update_body[0], **self.pending_update_body[1])

        self.pending_update_body = None
        self.pending_update = None


class VolumeService(Service):
    dismissed_import_jobs = set()

    @accepts(Str('volume'), Str('fs_type'), Str('dst_path'))
    @job(lock=lambda args: 'volume_import')
    async def import_(self, job, volume, fs_type, dst_path):
        job.set_progress(None, description="Mounting")

        src = os.path.join('/var/run/importcopy/tmpdir', os.path.relpath(volume, '/'))

        if os.path.exists(src):
            os.rmdir(src)

        try:
            os.makedirs(src)

            async with KernelModuleContextManager({"ntfs": "fuse"}.get(fs_type)):
                async with MountFsContextManager(volume, src, 'ro', fs_type):
                    job.set_progress(None, description="Importing")

                    line = [
                        '/usr/local/bin/rsync',
                        '--info=progress2',
                        '--modify-window=1',
                        '-rltvh',
                        '--no-perms',
                        src + '/',
                        dst_path
                    ]
                    rsync_proc = await Popen(
                        line, stdout=subprocess.PIPE, bufsize=0, preexec_fn=os.setsid,
                    )
                    stdout = b""
                    try:
                        progress_buffer = JobProgressBuffer(job)
                        while True:
                            line = await rsync_proc.stdout.readline()
                            if line:
                                stdout += line
                                try:
                                    proc_output = line.decode("utf-8", "ignore").strip()
                                    prog_out = proc_output.split(' ')
                                    progress = [x for x in prog_out if '%' in x]
                                    if len(progress):
                                        progress_buffer.set_progress(int(progress[0][:-1]))
                                    elif not proc_output.endswith('/'):
                                        if (
                                            proc_output not in ['sending incremental file list'] and
                                            'xfr#' not in proc_output
                                        ):
                                            progress_buffer.set_progress(None, extra=proc_output)
                                except Exception:
                                    logger.warning('Parsing error in rsync task', exc_info=True)
                            else:
                                break

                        progress_buffer.flush()
                        await rsync_proc.wait()
                        if rsync_proc.returncode != 0:
                            raise Exception("rsync failed with exit code %r" % rsync_proc.returncode)
                    except asyncio.CancelledError:
                        rsync_proc.kill()
                        raise

                    job.set_progress(100, description="Done", extra="")
                    return stdout.decode("utf-8", "ignore")
        finally:
            os.rmdir(src)

    """
    These methods are hacks for old UI which supports only one volume import at a time
    """

    async def get_current_import_job(self):
        import_jobs = await self.middleware.call('core.get_jobs', [('method', '=', 'volume.import_')])
        not_dismissed_import_jobs = [job for job in import_jobs if job["id"] not in self.dismissed_import_jobs]
        if not_dismissed_import_jobs:
            return not_dismissed_import_jobs[0]

    async def dismiss_current_import_job(self):
        current_import_job = await self.get_current_import_job()
        if current_import_job:
            self.dismissed_import_jobs.add(current_import_job["id"])
