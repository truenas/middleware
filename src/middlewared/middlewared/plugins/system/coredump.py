import datetime
import os

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
                timestamp = datetime.datetime.fromtimestamp(timestamp_us / 1_000_000)

                # query_journal runs journalctl --output=json and
                # all fields are always strings so we don't convert
                # them here since no caller (at time of writing)
                # depends on them being integers.
                coredump = {
                    "time": timestamp.strftime("%c"),
                    "pid": core.get("COREDUMP_PID", "0"),
                    "uid": core.get("COREDUMP_UID", "0"),
                    "gid": core.get("COREDUMP_GID", "0"),
                    "unit": core.get("COREDUMP_UNIT"),
                    "sig": core.get("COREDUMP_SIGNAL", "0"),
                    "exe": core.get("COREDUMP_EXE"),
                }
                filename = core.get("COREDUMP_FILENAME")
                if not filename or not isinstance(filename, str):
                    coredump["corefile"] = "none"
                else:
                    if os.path.exists(filename):
                        coredump["corefile"] = "present"
                    else:
                        coredump["corefile"] = "missing"
                coredumps.append(coredump)
        except Exception:
            self.logger.warning("Failed to obtain coredump information", exc_info=True)

        return coredumps
