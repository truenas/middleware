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
                coredump = {
                    "time": timestamp.strftime("%c"),
                    "pid": core["COREDUMP_PID"],
                    "uid": core["COREDUMP_UID"],
                    "gid": core["COREDUMP_GID"],
                    "unit": core.get("COREDUMP_UNIT"),
                    "sig": core["COREDUMP_SIGNAL"],
                    "exe": core.get("COREDUMP_EXE"),
                }
                filename = core.get("COREDUMP_FILENAME")
                if not filename:
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
