from datetime import datetime
import os
import textwrap

from middlewared.service import Service

SENTINEL_PATH = "/data/sentinels/unauthorized-reboot"
MIDDLEWARE_STARTED_SENTINEL_PATH = "/tmp/.middleware-started"


class UnauthorizedRebootAlertService(Service):
    async def terminate(self):
        if os.path.exists(SENTINEL_PATH):
            os.unlink(SENTINEL_PATH)


async def setup(middleware):
    if os.path.exists(SENTINEL_PATH):
        # We want to emit the mail only if the machine truly rebooted.
        if os.path.exists(MIDDLEWARE_STARTED_SENTINEL_PATH):
            return

        now = datetime.now().strftime("%c")

        # FIXME: Translation
        await middleware.call("mail.send", {
            "subject": "Unauthorized system reboot",
            "text": textwrap.dedent(f"""\
                System booted at {now} was not shut down properly
            """),
        })

    sentinel_dir = os.path.dirname(SENTINEL_PATH)
    if not os.path.exists(sentinel_dir):
        os.mkdir(sentinel_dir)

    with open(SENTINEL_PATH, "wb"):
        pass

    with open(MIDDLEWARE_STARTED_SENTINEL_PATH, "wb"):
        pass
