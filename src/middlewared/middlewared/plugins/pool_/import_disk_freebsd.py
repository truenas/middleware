import asyncio
import bsd
import os
import logging
import re
import subprocess

from middlewared.job import JobProgressBuffer
from middlewared.schema import Dict, Str
from middlewared.service import accepts, CallError, job, private, Service
from middlewared.utils import Popen, run

logger = logging.getLogger(__name__)


async def is_mounted(middleware, path):
    mounted = await middleware.run_in_thread(bsd.getmntinfo)
    return any(fs.dest == path for fs in mounted)


async def mount(device, path, fs_type, fs_options, options):
    options = options or []

    if isinstance(device, str):
        device = device.encode("utf-8")

    if isinstance(path, str):
        path = path.encode("utf-8")

    executable = "/sbin/mount"
    arguments = []

    if fs_type == "ntfs":
        executable = "/usr/local/bin/ntfs-3g"
    elif fs_type == "msdosfs" and fs_options:
        executable = "/sbin/mount_msdosfs"
        if fs_options.get("locale"):
            arguments.extend(["-L", fs_options["locale"]])
        arguments.extend(sum([["-o", option] for option in options], []))
        options = []
    else:
        arguments.extend(["-t", fs_type])

    if options:
        arguments.extend(["-o", ",".join(options)])

    proc = await Popen(
        [executable] + arguments + [device, path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf8",
    )
    output = await proc.communicate()

    if proc.returncode != 0:
        logger.debug("Mount failed (%s): %s", proc.returncode, output)
        raise ValueError("Mount failed (exit code {0}):\n{1}{2}" .format(
            proc.returncode,
            output[0].decode("utf-8"),
            output[1].decode("utf-8"),
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
        return (await run(
            'kldstat', '-n', self.module, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        ).returncode == 0


class MountFsContextManager:
    def __init__(self, middleware, device, path, *args, **kwargs):
        self.middleware = middleware
        self.device = device
        self.path = path
        self.args = args
        self.kwargs = kwargs

    async def __aenter__(self):
        await mount(self.device, self.path, *self.args, **self.kwargs)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if await is_mounted(self.middleware, self.path):
            await self.middleware.run_in_thread(bsd.unmount, self.path)


class PoolService(Service):

    dismissed_import_disk_jobs = set()

    @accepts(
        Str('device'),
        Str('fs_type'),
        Dict('fs_options', additional_attrs=True),
        Str('dst_path')
    )
    @job(lock=lambda args: 'volume_import', logs=True)
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
        job.set_progress(None, description="Mounting")

        src = os.path.join('/var/run/importcopy/tmpdir', os.path.relpath(device, '/'))

        if os.path.exists(src):
            os.rmdir(src)

        try:
            os.makedirs(src)

            async with KernelModuleContextManager({
                'ext2fs': 'ext2fs',
                'msdosfs': 'msdosfs_iconv',
                'ntfs': 'fuse'
            }.get(fs_type)):
                async with MountFsContextManager(self.middleware, device, src, fs_type, fs_options, ['ro']):
                    job.set_progress(None, description='Importing')

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
                        line, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0, preexec_fn=os.setsid,
                    )
                    try:
                        progress_buffer = JobProgressBuffer(job)
                        while True:
                            line = await rsync_proc.stdout.readline()
                            job.logs_fd.write(line)
                            if line:
                                try:
                                    line = line.decode("utf-8", "ignore").strip()
                                    bits = re.split(r"\s+", line)
                                    if len(bits) == 6 and bits[1].endswith("%") and bits[1][:-1].isdigit():
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
                            raise Exception("rsync failed with exit code %r" % rsync_proc.returncode)
                    except asyncio.CancelledError:
                        rsync_proc.kill()
                        raise

                    job.set_progress(100, description="Done", extra="")
        finally:
            os.rmdir(src)

    @accepts(Str("device"))
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

    @accepts()
    def import_disk_msdosfs_locales(self):
        """
        Get a list of locales for msdosfs type to be used in `pool.import_disk`.
        """
        return [
            locale.strip()
            for locale in subprocess.check_output(["locale", "-a"], encoding="utf-8").split("\n")
            if locale.strip() and locale.strip() not in ["C", "POSIX"]
        ]

    @private
    async def get_current_import_disk_job(self):
        import_jobs = await self.middleware.call('core.get_jobs', [('method', '=', 'pool.import_disk')])
        not_dismissed_import_jobs = [job for job in import_jobs if job["id"] not in self.dismissed_import_disk_jobs]
        if not_dismissed_import_jobs:
            return not_dismissed_import_jobs[0]

    @private
    async def dismiss_current_import_disk_job(self):
        current_import_job = await self.get_current_import_disk_job()
        if current_import_job:
            self.dismissed_import_disk_jobs.add(current_import_job["id"])
