import contextlib
import errno
import os
import re

from middlewared.schema import accepts, Ref, returns, Str
from middlewared.service import CallError, item_method, private, Service

from .utils import attachments_path

RE_ZD = re.compile(r'^/dev/zd[0-9]+$')


class PoolDatasetService(Service):

    class Config:
        namespace = 'pool.dataset'

    @item_method
    @accepts(Str('id', required=True))
    @returns(Ref('processes'))
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
        dataset = await self.middleware.call('pool.dataset.get_instance', oid)
        if dataset['locked']:
            return []
        path = attachments_path(dataset)
        zvol_path = f'/dev/zvol/{dataset["name"]}'
        return await self.middleware.call('pool.dataset.processes_using_paths', [path, zvol_path])

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
                        await self.middleware.call('service.restart', service)
                    else:
                        self.logger.info('Stopping service %r that holds dataset %r', service, oid)
                        await self.middleware.call('service.stop', service)
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
    def processes_using_paths(self, paths, include_paths=False):
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
                if not pid.isdigit() or int(pid) == os.getpid():
                    continue

                with contextlib.suppress(FileNotFoundError):
                    # FileNotFoundError for when a process is killed/exits
                    # while we're iterating
                    found = False
                    paths = set()
                    for f in os.listdir(f'/proc/{pid}/fd'):
                        fd = f'/proc/{pid}/fd/{f}'
                        if (
                            (include_devs and os.stat(fd).st_dev in include_devs) or
                            (exact_matches and os.path.islink(fd) and os.path.realpath(fd) in exact_matches)
                        ):
                            found = True
                            if os.path.islink(fd):
                                paths.add(os.path.realpath(fd))

                    if found:
                        with open(f'/proc/{pid}/status') as status:
                            name = status.readline().split('\t', 1)[1].strip()

                        proc = {'pid': pid, 'name': name}

                        if svc := self.middleware.call_sync('service.identify_process', name):
                            proc['service'] = svc
                        else:
                            with open(f'/proc/{pid}/cmdline') as cmd:
                                cmdline = cmd.read().replace('\u0000', ' ').strip()

                            proc['cmdline'] = cmdline

                        if include_paths:
                            proc['paths'] = sorted(paths)

                        result.append(proc)

        return result
