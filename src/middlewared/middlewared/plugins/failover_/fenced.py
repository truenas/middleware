import subprocess
import psutil
import contextlib
import os
import signal

from middlewared.service import Service, CallError
from fenced.fence import ExitCode as FencedExitCodes


PID_FILE = '/tmp/.fenced-pid'
IS_ALIVE_SIGNAL = 0


class FencedService(Service):

    class Config:
        private = True
        namespace = 'failover.fenced'

    def start(self, force=False, use_zpools=False):
        # get the boot disks so fenced doesn't try to
        # place reservations on the boot drives
        try:
            boot_disks = ','.join(self.middleware.call_sync('boot.get_disks'))
        except Exception:
            self.logger.warning('Failed to get boot disks', exc_info=True)
            # just because we can't grab the boot disks from middleware
            # doesn't mean we should fail to start fenced since it
            # (ultimately) prevents data corruption on HA systems
            boot_disks = ''

        # build the shell command
        cmd = ['fenced']
        if boot_disks:
            cmd.extend(['-ed', boot_disks])
        if force:
            cmd.append('-f')
        if use_zpools:
            cmd.append('-uz')

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out, err = proc.communicate()

        return proc.returncode

    def stop(self, banhammer=True):
        if banhammer:
            # dont care if it's running or not just
            # SIGKILL anything that has "fenced" in
            # the process name
            subprocess.run(['pkill', '-9', '-f', 'fenced'])
        else:
            res = self.middleware.call_sync('failover.fenced.run_info')
            if res['running'] and res['pid']:
                os.kill(res['pid'], signal.SIGKILL)

    def run_info(self):
        res = {'running': False, 'pid': ''}
        with contextlib.suppress(Exception):
            with open(PID_FILE, 'rb') as f:
                res['pid'] = int(f.read().decode())

        check_running_procs = False
        if res['pid']:
            try:
                os.kill(res['pid'], IS_ALIVE_SIGNAL)
            except OSError:
                check_running_procs = True
            else:
                res['running'] = True
        else:
            check_running_procs = True

        if check_running_procs:
            # either 1. no pid in file or 2. pid in file is wrong/stale
            _iter = psutil.process_iter
            proc = 'fenced'
            res['pid'] = next((p.pid for p in _iter() if p.name() == proc), '')
            res['running'] = bool(res['pid'])

        return res

    def signal(self, options):
        res = self.middleware.call_sync('failover.fenced.run_info')
        if res['running'] and res['pid']:
            try:
                if options.get('reload', False):
                    os.kill(res['pid'], signal.SIGHUP)
                if options.get('log_info', False):
                    os.kill(res['pid'], signal.SIGUSR1)
            except OSError as e:
                raise CallError(f'Failed to signal fenced: {e}')


async def hook_pool_event(middleware, *args, **kwargs):
    # only run this on SCALE Enterprise
    if await middleware.call('system.product_type') != 'SCALE_ENTERPRISE':
        return

    # HA licensed systems call fenced on their own
    if await middleware.call('failover.licensed'):
        return

    # only run this on the m/x series platform since the other
    # platforms are either non-supported or end of life
    if (await middleware.call('failover.ha_mode'))[0] not in ('ECHOWARP', 'PUMA'):
        return

    if (await middleware.call('failover.fenced.run_info'))['running']:
        try:
            await middleware.call('failover.fenced.signal', {'reload': True})
        except CallError as e:
            middleware.logger.error('Failed to reload fenced: %r', e)
    else:
        force = True
        use_zpools = True
        rc = await middleware.call('failover.fenced.start', force, use_zpools)
        if rc:
            for i in FencedExitCodes:
                if rc == i.value:
                    middleware.logger.error('Failed to start fenced: %s', i.name)
                    break


async def setup(middleware):
    middleware.register_hook('pool.post_create_or_update', hook_pool_event)
    middleware.register_hook('pool.post_import', hook_pool_event)
