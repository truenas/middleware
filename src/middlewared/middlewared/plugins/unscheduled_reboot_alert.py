from datetime import datetime
import os
import textwrap
import re

from middlewared.service import Service
from middlewared.client import Client

SENTINEL_PATH = "/data/sentinels/unscheduled-reboot"
MIDDLEWARE_STARTED_SENTINEL_PATH = "/tmp/.middleware-started"

# This file is managed in TrueNAS HA code (carp-state-change-hook.py)
# Ticket 39114
WATCHDOG_ALERT_FILE = "/data/sentinels/.watchdog-alert"

# This file is managed in TrueNAS HA code (.../sbin/fenced)
# Ticket 39114
FENCED_ALERT_FILE = "/data/sentinels/.fenced-alert"

# This file only exists on TrueNAS HA systems
# Ticket 39114
TRUENAS_HA_FILE = "/tmp/.ha_mode"


class UnscheduledRebootAlertService(Service):
    async def terminate(self):
        if os.path.exists(SENTINEL_PATH):
            os.unlink(SENTINEL_PATH)


async def setup(middleware):
    if os.path.exists(SENTINEL_PATH):
        # We want to emit the mail only if the machine truly rebooted
        if os.path.exists(MIDDLEWARE_STARTED_SENTINEL_PATH):
            return

        gc = await middleware.call('datastore.config', 'network.globalconfiguration')
        now = datetime.now().strftime("%c")

        Client() = c
        if not c.call('notifier.is_freenas') and c.call('notifier.failover_licensed')
            try:
                with open(TRUENAS_HA_FILE, "rb") as controller:
                    match = re.search(r"(.*):(.*)")
                if match.group(2) == 'B':
                    hostname = f"{gc['gc_hostname_b'].{gc['gc_domain']}"
            except IOError:
                pass
        else:
            hostname = f"{gc['gc_hostname']}.{gc.['gc_domain']}"

        # If the watchdog alert file exists,
        # then we can assume that carp-state-change-hook.py
        # panic'ed the box by design via a watchdog countdown.
        # Let's alert the end user why we did this
        if os.path.exists(WATCHDOG_ALERT_FILE) and not os.path.exists(FENCED_ALERT_FILE):
            await middleware.call("mail.send", {
                "subject": f"{hostname}: Failover event",
                "text": textwrap.dedent(f"""\
                    {hostname} had a failover event.
                    The system was rebooted to ensure a proper failover occurred.
                    The operating system successfully came back online at {now}.
                """),
            })

        # If the fenced alert file exists,
        # then we can assume that fenced panic'ed the box by design.
        # Let's alert the end user why we did this
        elif os.path.exists(FENCED_ALERT_FILE) and not os.path.exists(WATCHDOG_ALERT_FILE):
            await middleware.call("mail.send", {
                "subject": f"{hostname}: Failover event",
                "text": textwrap.dedent(f"""\
                    {hostname} had a failover event.
                    The system was rebooted because persistent SCSI reservations were lost and/or cleared.
                    The operating system successfully came back online at {now}.
                """),

            })

        # If both files exist, then something weird happened.
        # Get the modify time of the files, and send an email accordingly
        elif os.path.exists(WATCHDOG_ALERT_FILE) and os.path.exists(FENCED_ALERT_FILE):
            watchdog_time = os.path.getmtime(WATCHDOG_ALERT_FILE)
            fenced_time = os.path.getmtime(FENCED_ALERT_FILE)
            if (watchdog_time > fenced_time):
                await middleware.call("mail.send", {
                    "subject": f"{hostname}: Failover event",
                    "text": textwrap.dedent(f"""\
                        {hostname} had a failover event.
                        The system was rebooted to ensure a proper failover occurred.
                        The operating system successfully came back online at {now}.
                    """),

                })

            else:
                await middleware.call("mail.send", {
                    "subject": f"{hostname}: Failover event",
                    "text": textwrap.dedent(f"""\
                        {hostname} had a failover event.
                        The system was rebooted because persistent SCSI reservations were lost and/or cleared.
                        The operating system successfully came back online at {now}.
                    """),
                })

        else:
            await middleware.call("mail.send", {
                "subject": f"{hostname}: Unscheduled system reboot",
                "text": textwrap.dedent(f"""\
                    {hostname} had an unscheduled system reboot.
                    The operating system successfully came back online at {now}.
                """),
            })

    # Clean up the files after we have alerted accordingly so we don't keep sending an email unnecessarily
    try:
        os.unlink(FENCED_ALERT_FILE)
    except IOError:
        pass
    try:
        os.unlink(WATCHDOG_ALERT_FILE)
    except IOError:
        pass

    sentinel_dir = os.path.dirname(SENTINEL_PATH)
    if not os.path.exists(sentinel_dir):
        os.mkdir(sentinel_dir)

    with open(SENTINEL_PATH, "wb"):
        pass

    with open(MIDDLEWARE_STARTED_SENTINEL_PATH, "wb"):
        pass
