from datetime import datetime
import os
import textwrap
import time

from middlewared.service import Service

SENTINEL_PATH = "/data/sentinels/unauthorized-reboot"


class UnauthorizedRebootAlertService(Service):
    async def terminate(self):
        if os.path.exists(SENTINEL_PATH):
            os.unlink(SENTINEL_PATH)


async def setup(middleware):
    if os.path.exists(SENTINEL_PATH):

        # If uptime is bigger than 3 minutes its likely middleware crashed.
        # We want to emit the mail only if the machine truly rebooted.
        uptime = time.clock_gettime(5)  # CLOCK_UPTIME = 5
        if uptime > 180:
            return
        gc = await middleware.call('datastore.config', 'network.globalconfiguration')

        hostname = f"{gc['gc_hostname']}.{gc['gc_domain']}"
        now = datetime.now().strftime("%c")

        # FIXME: Translation
        await middleware.call("mail.send", {
            "subject": f"{hostname}: Unauthorized system reboot",
            "text": textwrap.dedent(f"""\
                System booted at {now} was not shut down properly
            """),
        })

    sentinel_dir = os.path.dirname(SENTINEL_PATH)
    if not os.path.exists(sentinel_dir):
        os.mkdir(sentinel_dir)

    with open(SENTINEL_PATH, "wb"):
        pass
