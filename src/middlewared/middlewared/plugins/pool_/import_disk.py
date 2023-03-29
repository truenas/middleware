import os
import logging
import re
import subprocess
import time

import psutil

from middlewared.job import JobProgressBuffer
from middlewared.schema import accepts, Dict, List, returns, Str
from middlewared.service import CallError, job, Service

logger = logging.getLogger(__name__)


def is_mounted(path):
    mounted = psutil.disk_partitions()
    return any(fs.mountpoint == path for fs in mounted)


def mount(device, path, fs_type, fs_options, options):
    options = options or []

    if isinstance(device, str):
        device = device.encode("utf-8")

    if isinstance(path, str):
        path = path.encode("utf-8")

    executable = "mount"
    arguments = []

    if fs_type == "msdosfs" and fs_options:
        if fs_options.get("locale"):
            if fs_options.get("locale") == "utf8":
                options.append("utf8")
            else:
                options.append(f"iocharset={fs_options['locale']}")

    arguments.extend(["-t", {"msdosfs": "vfat", "ext2fs": "ext2"}.get(fs_type, fs_type)])

    if options:
        arguments.extend(["-o", ",".join(options)])

    proc = subprocess.Popen(
        [executable] + arguments + [device, path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    output = proc.communicate()

    if proc.returncode != 0:
        raise CallError("Mount failed (exit code {0}):\n{1}{2}" .format(
            proc.returncode,
            output[0].decode("utf-8"),
            output[1].decode("utf-8"),
        ))
    else:
        return True


class MountFsContextManager:
    def __init__(self, middleware, device, path, *args, **kwargs):
        self.middleware = middleware
        self.device = device
        self.path = path
        self.args = args
        self.kwargs = kwargs

    def __enter__(self):
        os.makedirs(self.path, exist_ok=True)
        mount(self.device, self.path, *self.args, **self.kwargs)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if is_mounted(os.path.realpath(self.path)):
            subprocess.check_call(["umount", self.path])
        os.rmdir(self.path)


class PoolService(Service):

    RE_NLS = re.compile(r"nls_(.+)\.ko")

    @accepts(
        Str('device'),
        Str('fs_type', enum=['ext2fs', 'msdosfs', 'ntfs', 'ufs']),
        Dict('fs_options', additional_attrs=True),
        Str('dst_path')
    )
    @returns()
    @job(lock=lambda args: 'volume_import', logs=True, abortable=True)
    def import_disk(self, job, device, fs_type, fs_options, dst_path):
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
                    "/dev/sda", "msdosfs", {}, "/mnt/tank/mydisk"
                ]
            }
        """
        job.set_progress(None, description='Mounting')

        src = os.path.join('/var/run/importcopy/tmpdir', os.path.relpath(device, '/'))

        with MountFsContextManager(self.middleware, device, src, fs_type, fs_options, ['ro']):
            job.set_progress(None, description='Importing')

            line = [
                'rsync',
                '--info=progress2',
                '--modify-window=1',
                '-rltvhX',
                '--no-perms',
                src + '/',
                dst_path
            ]
            rsync_proc = subprocess.Popen(
                line, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=0, preexec_fn=os.setsid,
            )
            try:
                progress_buffer = JobProgressBuffer(job)
                percent_complete = 0
                while True:
                    line = rsync_proc.stdout.readline()
                    job.logs_fd.write(line)
                    if line:
                        try:
                            line = line.decode('utf-8', 'ignore').strip()
                            bits = re.split(r'\s+', line)
                            if len(bits) == 6 and bits[1].endswith('%') and bits[1][:-1].isdigit():
                                percent_complete = int(bits[1][:-1])
                                progress_buffer.set_progress(percent_complete)
                            elif not line.endswith('/'):
                                if (
                                    line not in ['sending incremental file list'] and
                                    'xfr#' not in line
                                ):
                                    progress_buffer.set_progress(percent_complete, extra=line)
                        except Exception:
                            logger.warning('Parsing error in rsync task', exc_info=True)
                    else:
                        break

                progress_buffer.flush()
                rsync_proc.wait()
                if rsync_proc.returncode != 0:
                    raise CallError('rsync failed with exit code %r' % rsync_proc.returncode)
            finally:
                if rsync_proc.returncode is None:
                    try:
                        logger.warning("Terminating rsync")
                        rsync_proc.terminate()
                        try:
                            rsync_proc.wait(10)
                        except subprocess.TimeoutExpired:
                            logger.warning("Timeout waiting for rsync to terminate, killing it")
                            rsync_proc.kill()
                            time.sleep(5)  # For children to die before unmount
                    except ProcessLookupError:
                        logger.warning("rsync process lookup error")

            job.set_progress(100, description='Done', extra='')

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
                "params": ["/dev/sda"]
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
    @returns(List('locales', items=[Str('locale')]))
    def import_disk_msdosfs_locales(self):
        """
        Get a list of locales for msdosfs type to be used in `pool.import_disk`.
        """
        result = {"utf8"}
        kernel = subprocess.check_output(["uname", "-r"], encoding="utf8").strip()
        for name in os.listdir(os.path.join("/lib/modules", kernel, "kernel/fs/nls")):
            m = self.RE_NLS.match(name)
            if m:
                result.add(m.group(1))

        return sorted(result)
