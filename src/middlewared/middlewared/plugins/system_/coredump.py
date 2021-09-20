from os.path import exists
from systemd import journal

from middlewared.service import private, Service


class SystemService(Service):

    @private
    def coredumps(self):
        coredumps = []

        try:
            with journal.Reader() as reader:
                reader.add_match(CODE_FUNC='submit_coredump')
                for core in reader:
                    coredumps.append({
                        'time': core['COREDUMP_TIMESTAMP'].strftime('%c'),
                        'pid': core['COREDUMP_PID'],
                        'uid': core['COREDUMP_UID'],
                        'gid': core['COREDUMP_GID'],
                        'unit': core['COREDUMP_UNIT'],
                        'sig': core['COREDUMP_SIGNAL'],
                        'corefile': 'present' if exists(core['COREDUMP_FILENAME']) else 'missing',
                        'exe': core['COREDUMP_EXE'],
                    })
        except Exception:
            self.logger.warning('Failed to obtain coredump information', exc_info=True)

        return coredumps
