from __future__ import annotations

import contextlib
import errno
import os
import re
from typing import TYPE_CHECKING

from middlewared.plugins.zfs_.utils import zvol_name_to_path
from middlewared.service import CallError

if TYPE_CHECKING:
    from middlewared.service import ServiceContext

from .utils import dataset_mountpoint

RE_ZD = re.compile(r'^/dev/zd[0-9]+$')


async def processes_impl(ctx: ServiceContext, oid: str) -> list[dict]:
    dataset = await ctx.call2(ctx.s.pool.dataset.get_instance_quick, oid, {'encryption': True})
    if dataset.locked:
        return []

    paths = [zvol_name_to_path(dataset.name)]
    if mountpoint := dataset_mountpoint(dataset):
        paths.append(mountpoint)

    return await ctx.call2(ctx.s.pool.dataset.processes_using_paths, paths)


async def kill_processes(ctx: ServiceContext, oid: str, control_services: bool, max_tries: int = 5) -> None:
    need_restart_services = []
    need_stop_services = []
    midpid = os.getpid()
    for process in await ctx.call2(ctx.s.pool.dataset.processes, oid):
        service = process.get('service')
        if service is not None:
            if any(
                attachment_delegate.service == service
                for attachment_delegate in await ctx.call2(ctx.s.pool.dataset.get_attachment_delegates)
            ):
                need_restart_services.append(service)
            else:
                need_stop_services.append(service)
    if (need_restart_services or need_stop_services) and not control_services:
        raise CallError('Some services have open files and need to be restarted or stopped', errno.EBUSY, {
            'code': 'control_services',
            'restart_services': need_restart_services,
            'stop_services': need_stop_services,
            'services': need_restart_services + need_stop_services,
        })

    for i in range(max_tries):
        processes = await ctx.call2(ctx.s.pool.dataset.processes, oid)
        if not processes:
            return

        for process in processes:
            if process['pid'] == midpid:
                ctx.logger.warning(
                    'The main middleware process %r (%r) currently is holding dataset %r',
                    process['pid'], process['cmdline'], oid
                )
                continue

            service = process.get('service')
            if service is not None:
                if any(
                    attachment_delegate.service == service
                    for attachment_delegate in await ctx.call2(ctx.s.pool.dataset.get_attachment_delegates)
                ):
                    ctx.logger.info('Restarting service %r that holds dataset %r', service, oid)
                    await (await ctx.middleware.call('service.control', 'RESTART', service)).wait(raise_error=True)
                else:
                    ctx.logger.info('Stopping service %r that holds dataset %r', service, oid)
                    await (await ctx.middleware.call('service.control', 'STOP', service)).wait(raise_error=True)
            else:
                ctx.logger.info('Killing process %r (%r) that holds dataset %r', process['pid'],
                                 process['cmdline'], oid)
                try:
                    await ctx.middleware.call('service.terminate_process', process['pid'])
                except CallError as e:
                    ctx.logger.warning('Error killing process: %r', e)

    processes = await ctx.call2(ctx.s.pool.dataset.processes, oid)
    if not processes:
        return

    ctx.logger.info('The following processes don\'t want to stop: %r', processes)
    raise CallError('Unable to stop processes that have open files', errno.EBUSY, {
        'code': 'unstoppable_processes',
        'processes': processes,
    })


def processes_using_paths(
    ctx: ServiceContext,
    paths: list[str],
    include_paths: bool = False,
    include_middleware: bool = False
) -> list[dict]:
    exact_matches = set()
    include_devs = []
    for path in paths:
        if RE_ZD.match(path):
            exact_matches.add(path)
        else:
            try:
                if path.startswith("/dev/zvol/"):
                    if os.path.isdir(path):
                        for root, dirs, files in os.walk(path):
                            for f in files:
                                exact_matches.add(os.path.realpath(os.path.join(root, f)))
                    else:
                        exact_matches.add(os.path.realpath(path))
                else:
                    include_devs.append(os.stat(path).st_dev)
            except FileNotFoundError:
                continue

    result = []
    if include_devs or exact_matches:
        for pid in os.listdir('/proc'):
            if not pid.isdigit() or (not include_middleware and (int(pid) == os.getpid())):
                continue

            with contextlib.suppress(FileNotFoundError, ProcessLookupError):
                found = False
                found_paths = set()
                for f in os.listdir(f'/proc/{pid}/fd'):
                    fd = f'/proc/{pid}/fd/{f}'
                    is_link = False
                    realpath = None
                    with contextlib.suppress(FileNotFoundError, PermissionError):
                        if (
                            (include_devs and os.stat(fd).st_dev in include_devs) or
                            (
                                exact_matches and
                                (is_link := os.path.islink(fd)) and
                                (realpath := os.path.realpath(fd)) in exact_matches
                            )
                        ):
                            found = True
                            if include_paths:
                                if is_link:
                                    found_paths.add(realpath)
                                else:
                                    found_paths.add(os.readlink(fd))

                if found:
                    with open(f'/proc/{pid}/comm') as comm:
                        name = comm.read().strip()

                    proc = {'pid': int(pid), 'name': name, 'service': None, 'cmdline': None}

                    if svc := ctx.middleware.call_sync('service.identify_process', name):
                        proc['service'] = svc
                    else:
                        with open(f'/proc/{pid}/cmdline') as cmd:
                            cmdline = cmd.read().replace('\u0000', ' ').strip()

                        proc['cmdline'] = cmdline

                    if include_paths:
                        proc['paths'] = sorted(found_paths)

                    result.append(proc)

    return result
