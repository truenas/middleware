# -*- coding=utf-8 -*-
import contextlib
import logging
import os
import re
import socket
import subprocess
import time

from middlewared.client import Client

logger = logging.getLogger(__name__)


def main():
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")

    interval = 10
    logger.info("Probing middleware accessibility with %d seconds interval", interval)
    while True:
        try:
            with Client():
                pass
        except socket.timeout:
            logger.info("Caught timeout, dumping core")
            dump_core()
            break
        else:
            time.sleep(interval)


def dump_core():
    middlewared_pid = int(
        re.match(
            r"MainPID=([0-9]+)",
            subprocess.check_output(
                "systemctl show --property MainPID middlewared".split(),
                encoding="utf-8",
            ),
        ).group(1),
    )
    logger.info("middlewared PID: %d", middlewared_pid)

    core_file = f"core.{middlewared_pid}"
    with contextlib.suppress(FileNotFoundError):
        os.unlink(core_file)
    subprocess.run(
        ["gdb", "-p", str(middlewared_pid), "-batch", "-ex", "generate-core-file"],
        check=True,
    )

    logger.info("Compressing core file %r", core_file)
    subprocess.run(["gzip", core_file], check=True)
    logger.info("%r is ready!", f"{core_file}.gz")


if __name__ == "__main__":
    main()
