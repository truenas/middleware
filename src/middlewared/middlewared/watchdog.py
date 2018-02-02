import argparse
import logging
import psutil
import signal
import time

from . import Client


def main():
    logging.basicConfig(level=logging.DEBUG)

    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", default=60, type=int)
    parser.add_argument("--failures", default=5, type=int)
    parser.add_argument("--post-kill", default=120, type=int)
    args = parser.parse_args()

    while True:
        time.sleep(args.interval)

        for i in range(args.failures):
            try:
                with Client() as c:
                    c.call("core.ping")
                    break
            except Exception as e:
                logging.info("Failed attempt #%d: %r", i + 1, e)
        else:
            logging.warning("Enough failed attempts, restarting middlewared")
            processes = [p for p in psutil.process_iter(attrs=["pid", "cmdline"])
                         if p.cmdline() and p.cmdline()[-1].endswith(": middlewared")]
            for process in processes:
                logging.warning("Killing %d", process.pid)
                try:
                    process.send_signal(signal.SIGKILL)
                except Exception as e:
                    logging.warning("%r", e)

            time.sleep(args.post_kill)


if __name__ == "__main__":
    main()
