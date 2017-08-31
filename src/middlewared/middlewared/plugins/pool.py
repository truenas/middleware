import asyncio
import logging
from datetime import datetime
import os
import subprocess
import sysctl

import bsd
import libzfs

from middlewared.job import JobProgressBuffer
from middlewared.schema import accepts, Int, Str
from middlewared.service import filterable, item_method, job, private, CRUDService
from middlewared.utils import Popen, run

logger = logging.getLogger(__name__)


async def is_mounted(middleware, path):
    mounted = await middleware.threaded(bsd.getmntinfo)
    return any(fs.dest == path for fs in mounted)


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
    def __init__(self, middleware, dev, path, *args):
        self.middleware = middleware
        self.dev = dev
        self.path = path
        self.args = args

    async def __aenter__(self):
        await mount(self.dev, self.path, *self.args)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if await is_mounted(self.middleware, self.path):
            await self.middleware.threaded(bsd.unmount, self.path)


class PoolService(CRUDService):

    @filterable
    async def query(self, filters=None, options=None):
        filters = filters or []
        options = options or {}
        options['extend'] = 'pool.pool_extend'
        options['prefix'] = 'vol_'
        return await self.middleware.call('datastore.query', 'storage.volume', filters, options)

    @private
    async def pool_extend(self, pool):
        pool.pop('fstype', None)

        """
        If pool is encrypted we need to check if the pool is imported
        or if all geli providers exist.
        """
        try:
            zpool = libzfs.ZFS().get(pool['name'])
        except libzfs.ZFSException:
            zpool = None

        if zpool:
            pool['status'] = zpool.status
            pool['scan'] = zpool.scrub.__getstate__()
        else:
            pool.update({
                'status': 'OFFLINE',
                'scan': None,
            })

        if pool['encrypt'] > 0:
            if zpool:
                pool['is_decrypted'] = True
            else:
                decrypted = True
                for ed in await self.middleware.call('datastore.query', 'storage.encrypteddisk', [('encrypted_volume', '=', pool['id'])]):
                    if not os.path.exists(f'/dev/{ed["encrypted_provider"]}.eli'):
                        decrypted = False
                        break
                pool['is_decrypted'] = decrypted
        else:
            pool['is_decrypted'] = True
        return pool

    @item_method
    @accepts(Int('id'))
    async def get_disks(self, oid):
        """
        Get all disks from a given pool `id`.
        """
        pool = await self.query([('id', '=', oid)], {'get': True})
        if not pool['is_decrypted']:
            yield
        async for i in await self.middleware.call('zfs.pool.get_disks', pool['name']):
            yield i

    @private
    def configure_resilver_priority(self):
        """
        Configure resilver priority based on user selected off-peak hours.
        """
        resilver = self.middleware.call_sync('datastore.config', 'storage.resilver')

        if not resilver['enabled'] or not resilver['weekday']:
            return

        higher_prio = False
        weekdays = map(lambda x: int(x), resilver['weekday'].split(','))
        now = datetime.now()
        now_t = now.time()
        # end overlaps the day
        if resilver['begin'] > resilver['end']:
            if now.isoweekday() in weekdays and now_t >= resilver['begin']:
                higher_prio = True
            else:
                lastweekday = now.isoweekday() - 1
                if lastweekday == 0:
                    lastweekday = 7
                if lastweekday in weekdays and now_t < resilver['end']:
                    higher_prio = True
        # end does not overlap the day
        else:
            if now.isoweekday() in weekdays and now_t >= resilver['begin'] and now_t < resilver['end']:
                higher_prio = True

        if higher_prio:
            resilver_delay = 0
            resilver_min_time_ms = 9000
            scan_idle = 0
        else:
            resilver_delay = 2
            resilver_min_time_ms = 3000
            scan_idle = 50

        sysctl.filter('vfs.zfs.resilver_delay')[0].value = resilver_delay
        sysctl.filter('vfs.zfs.resilver_min_time_ms')[0].value = resilver_min_time_ms
        sysctl.filter('vfs.zfs.scan_idle')[0].value = scan_idle

    @accepts(Str('volume'), Str('fs_type'), Str('dst_path'))
    @job(lock=lambda args: 'volume_import')
    async def import_disk(self, job, volume, fs_type, dst_path):
        job.set_progress(None, description="Mounting")

        src = os.path.join('/var/run/importcopy/tmpdir', os.path.relpath(volume, '/'))

        if os.path.exists(src):
            os.rmdir(src)

        try:
            os.makedirs(src)

            async with KernelModuleContextManager({"ntfs": "fuse"}.get(fs_type)):
                async with MountFsContextManager(self.middleware, volume, src, 'ro', fs_type):
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

    dismissed_import_disk_jobs = set()

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


def setup(middleware):
    asyncio.ensure_future(middleware.call('pool.configure_resilver_priority'))
