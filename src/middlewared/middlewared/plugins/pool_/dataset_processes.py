import contextlib
import errno
import os
import re

from middlewared.api import api_method
from middlewared.api.current import PoolDatasetProcessesArgs, PoolDatasetProcessesResult
from middlewared.plugins.zfs_.utils import zvol_name_to_path
from middlewared.service import CallError, item_method, private, Service

from .utils import dataset_mountpoint

RE_ZD = re.compile(r'^/dev/zd[0-9]+$')


class PoolDatasetService(Service):

    class Config:
        namespace = 'pool.dataset'

    @item_method
    @api_method(PoolDatasetProcessesArgs, PoolDatasetProcessesResult, roles=['DATASET_READ'])
    async def processes(self, oid):
        """
        Return a list of processes using this dataset.

        Example return value:

        [
          {
            "pid": 2520,
            "name": "smbd",
            "service": "cifs"
          },
          {
            "pid": 97778,
            "name": "minio",
            "cmdline": "/usr/local/bin/minio -C /usr/local/etc/minio server --address=0.0.0.0:9000 --quiet /mnt/tank/wk"
          }
        ]
        """
        dataset = await self.middleware.call('pool.dataset.get_instance_quick', oid, {'encryption': True})
        if dataset['locked']:
            return []

        paths = [zvol_name_to_path(dataset['name'])]
        if mountpoint := dataset_mountpoint(dataset):
            paths.append(mountpoint)

        return await self.middleware.call('pool.dataset.processes_using_paths', paths)

    @private
    async def kill_processes(self, oid, control_services, max_tries=5):
        need_restart_services = []
        need_stop_services = []
        midpid = os.getpid()
        for process in await self.middleware.call('pool.dataset.processes', oid):
            service = process.get('service')
            if service is not None:
                if any(
                    attachment_delegate.service == service
                    for attachment_delegate in await self.middleware.call('pool.dataset.get_attachment_delegates')
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
            processes = await self.middleware.call('pool.dataset.processes', oid)
            if not processes:
                return

            for process in processes:
                if process['pid'] == midpid:
                    self.logger.warning(
                        'The main middleware process %r (%r) currently is holding dataset %r',
                        process['pid'], process['cmdline'], oid
                    )
                    continue

                service = process.get('service')
                if service is not None:
                    if any(
                        attachment_delegate.service == service
                        for attachment_delegate in await self.middleware.call('pool.dataset.get_attachment_delegates')
                    ):
                        self.logger.info('Restarting service %r that holds dataset %r', service, oid)
                        await (await self.middleware.call('service.control', 'RESTART', service)).wait(raise_error=True)
                    else:
                        self.logger.info('Stopping service %r that holds dataset %r', service, oid)
                        await (await self.middleware.call('service.control', 'STOP', service)).wait(raise_error=True)
                else:
                    self.logger.info('Killing process %r (%r) that holds dataset %r', process['pid'],
                                     process['cmdline'], oid)
                    try:
                        await self.middleware.call('service.terminate_process', process['pid'])
                    except CallError as e:
                        self.logger.warning('Error killing process: %r', e)

        processes = await self.middleware.call('pool.dataset.processes', oid)
        if not processes:
            return

        self.logger.info('The following processes don\'t want to stop: %r', processes)
        raise CallError('Unable to stop processes that have open files', errno.EBUSY, {
            'code': 'unstoppable_processes',
            'processes': processes,
        })

    @private
    def processes_using_paths(self, paths, include_paths=False, include_middleware=False):
        """
        Find processes using paths supplied via `paths`. Path may be an absolute path for
        a directory (e.g. /var/db/system) or a path in /dev/zvol or /dev/zd*

        `include_paths`: include paths that are open by the process in output. By default
        this is not included in output for performance reasons.

        `include_middleware`: include files opened by the middlewared process in output.
        These are not included by default.
        """
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
                    # FileNotFoundError for when a process is killed/exits
                    # while we're iterating
                    found = False
                    found_paths = set()
                    for f in os.listdir(f'/proc/{pid}/fd'):
                        fd = f'/proc/{pid}/fd/{f}'
                        is_link = False
                        realpath = None
                        # stat(2) from host may fail with EACCES if file is inside private mount
                        # namespace in a container. An example of why this can happen is if file is
                        # in snap installed in an Ubuntu container.
                        with contextlib.suppress(FileNotFoundError, PermissionError):
                            # Have second suppression here so that we don't lose list of files
                            # if we have TOCTOU issue on one of files.
                            #
                            # We want to include file in list of paths in the following
                            # situations:
                            #
                            # 1. File is regular file and has same device id as specified path
                            # 2. File is a symbolic link and exactly matches a provided /dev/zvol or /dev/zd path
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
                                        # This is a path in `/dev/zvol` or `/dev/zd*`
                                        found_paths.add(realpath)
                                    else:
                                        # We need to readlink to convert `/proc/<pid>/fd/<fd>` to
                                        # the file's path name.
                                        found_paths.add(os.readlink(fd))

                    if found:
                        with open(f'/proc/{pid}/comm') as comm:
                            name = comm.read().strip()

                        proc = {'pid': int(pid), 'name': name, 'service': None, 'cmdline': None}

                        if svc := self.middleware.call_sync('service.identify_process', name):
                            proc['service'] = svc
                        else:
                            with open(f'/proc/{pid}/cmdline') as cmd:
                                cmdline = cmd.read().replace('\u0000', ' ').strip()

                            proc['cmdline'] = cmdline

                        if include_paths:
                            proc['paths'] = sorted(found_paths)

                        result.append(proc)

        return result
