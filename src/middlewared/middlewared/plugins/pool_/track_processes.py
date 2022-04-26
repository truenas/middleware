import contextlib
import os
import re

from middlewared.service import private, Service

RE_ZD = re.compile(r"^/dev/zd[0-9]+$")


class PoolDatasetService(Service):

    class Config:
        namespace = 'pool.dataset'

    @private
    def processes_using_paths(self, paths):
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
                    for f in os.listdir(f'/proc/{pid}/fd'):
                        fd = f'/proc/{pid}/fd/{f}'
                        if (
                            (include_devs and os.stat(fd).st_dev in include_devs) or
                            (exact_matches and os.path.islink(fd) and os.path.realpath(fd) in exact_matches)
                        ):
                            with open(f'/proc/{pid}/status') as status:
                                name = status.readline().split('\t', 1)[1].strip()
                                if svc := self.middleware.call_sync('service.identify_process', name):
                                    result.append({'pid': pid, 'name': name, 'service': svc})
                                else:
                                    with open(f'/proc/{pid}/cmdline') as cmd:
                                        cmdline = cmd.read().replace('\u0000', ' ').strip()
                                        result.append({'pid': pid, 'name': name, 'cmdline': cmdline})

        return result
