from datetime import datetime
import os
import socket
import textwrap

from middlewared.service import Service

SENTINEL_PATH = "/data/sentinels/unauthorized-reboot"


class UnauthorizedRebootAlertService(Service):
    async def terminate(self):
        if os.path.exists(SENTINEL_PATH):
            os.unlink(SENTINEL_PATH)


async def setup(middleware):
    if os.path.exists(SENTINEL_PATH):
        hostname = socket.gethostname()
        now = datetime.now().strftime("%c")

        # FIXME: Translation
        await middleware.call("mail.send", {
            "subject": f"{hostname}: Unauthorized system reboot",
            "text": textwrap.dedent(f"""\
                System booted at {now} was not shut down properly
            """),
        })

    with open(SENTINEL_PATH, "wb"):
        pass
