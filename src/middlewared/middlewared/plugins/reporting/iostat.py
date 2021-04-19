import logging
import subprocess
import time

from middlewared.utils import start_daemon_thread

logger = logging.getLogger(__name__)


class DiskStats:
    def __init__(self, interval):
        self.interval = interval
        self.process = None
        self.run = True
        self.stats = {}
        start_daemon_thread(target=self._read)

    def _read(self):
        while self.run:
            try:
                self.process = subprocess.Popen([
                    "iostat",
                    "-d",  # Display only device statistics.
                    "-I",  # Display total statistics for a given time period
                    "-w", f"{self.interval}",  # Pause `wait` seconds between each display.
                    "-x",  # Show extended disk statistics
                ], encoding="utf-8", errors="ignore", stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                i = 0
                stats = {}
                while True:
                    line = self.process.stdout.readline()
                    if not line:
                        break

                    try:
                        device, read_ops, write_ops, read_kbytes, write_kbytes, _, _, busy = line.split()
                    except ValueError:
                        # "extended device statistics" header
                        i += 1
                        if i > 2:  # Do not send first read results
                            self.stats = stats
                            stats = {}
                    else:
                        if device.startswith(("ada", "da", "nvd")):
                            stats[device] = {
                                "read_ops": int(float(read_ops)),
                                "read_bytes": int(float(read_kbytes) * 1024),
                                "write_ops": int(float(write_ops)),
                                "write_bytes": int(float(write_kbytes) * 1024),
                                "busy": float(busy) / self.interval,
                            }
            except Exception:
                logger.error("Unhandled exception in DiskStats", exc_info=True)
                time.sleep(self.interval)

    def read(self):
        read_ops = 0
        read_bytes = 0
        write_ops = 0
        write_bytes = 0
        busy = 0
        count = 0
        for disk, current in self.stats.items():
            read_ops += current["read_ops"]
            read_bytes += current["read_bytes"]
            write_ops += current["write_ops"]
            write_bytes += current["write_bytes"]
            busy += current["busy"]
            count += 1

        return {
            "read_ops": read_ops,
            "read_bytes": read_bytes,
            "write_ops": write_ops,
            "write_bytes": write_bytes,
            "busy": busy / count if count else 0,
        }

    def stop(self):
        self.run = False
        try:
            self.process.kill()
        except ProcessLookupError:
            pass
