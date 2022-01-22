import os
import contextlib

from middlewared.service import CRUDService, private


class PoolDatasetService(CRUDService):

    @private
    def processes_using_paths(self, paths):
        include_devs = []
        for path in paths:
            try:
                include_devs.append(os.stat(path).st_dev)
            except FileNotFoundError:
                continue

        result = []
        if include_devs:
            for pid in os.listdir('/proc'):
                if not pid.isdigit() or int(pid) == os.getpid():
                    continue

                with contextlib.suppress(FileNotFoundError):
                    # FileNotFoundError for when a process is killed/exits
                    # while we're iterating
                    for f in os.listdir(f'/proc/{pid}/fd'):
                        if os.stat(f'/proc/{pid}/fd/{f}').st_dev in include_devs:
                            with open(f'/proc/{pid}/status') as status:
                                name = status.readline().split('\t', 1)[1].strip()
                                if svc := self.middleware.call_sync('service.identify_process', name):
                                    result.append({'pid': pid, 'name': name, 'service': svc})
                                else:
                                    with open(f'/proc/{pid}/cmdline') as cmd:
                                        cmdline = cmd.read().replace('\u0000', ' ').strip()
                                        result.append({'pid': pid, 'name': name, 'cmdline': cmdline})
        return result
