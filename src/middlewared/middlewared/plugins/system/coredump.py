from datetime import datetime
from os.path import exists

from middlewared.service import private, Service
from middlewared.utils.journal import query_journal


class SystemService(Service):

    @private
    def coredumps(self):
        coredumps = []

        try:
            for core in query_journal(["CODE_FUNC=submit_coredump"]):
                # COREDUMP_TIMESTAMP is in microseconds since epoch
                timestamp_us = int(core.get("COREDUMP_TIMESTAMP", 0))
                timestamp = datetime.fromtimestamp(timestamp_us / 1_000_000)

                coredump = {
                    'time': timestamp.strftime('%c'),
                    'pid': int(core.get('COREDUMP_PID', 0)),
                    'uid': int(core.get('COREDUMP_UID', 0)),
                    'gid': int(core.get('COREDUMP_GID', 0)),
                    'unit': core.get('COREDUMP_UNIT'),
                    'sig': int(core.get('COREDUMP_SIGNAL', 0)),
                    'exe': core.get('COREDUMP_EXE'),
                }
                filename = core.get('COREDUMP_FILENAME')
                if not filename or not isinstance(filename, str):
                    coredump['corefile'] = 'none'
                else:
                    coredump['corefile'] = 'present' if exists(filename) else 'missing'
                coredumps.append(coredump)
        except Exception:
            self.logger.warning('Failed to obtain coredump information', exc_info=True)

        return coredumps
