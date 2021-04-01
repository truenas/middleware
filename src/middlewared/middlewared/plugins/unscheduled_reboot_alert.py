from datetime import datetime
import os
import textwrap
import struct

from middlewared.alert.base import AlertCategory, AlertClass, SimpleOneShotAlertClass, AlertLevel
from middlewared.service import Service

SENTINEL_PATH = "/data/sentinels/unscheduled-reboot"
MIDDLEWARE_STARTED_SENTINEL_PATH = "/tmp/.middleware-started"

# This file is managed in TrueNAS HA code (carp-state-change-hook.py)
# Ticket 39114
WATCHDOG_ALERT_FILE = "/data/sentinels/.watchdog-alert"

# This file is managed in TrueNAS HA code (.../sbin/fenced)
# Ticket 39114
FENCED_ALERT_FILE = "/data/sentinels/.fenced-alert"


class UnscheduledRebootAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = "Unscheduled System Reboot"
    text = "%s"

    deleted_automatically = False


class UnscheduledRebootAlertService(Service):

    class Config:
        private = True

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
        hostname = f"{gc['gc_hostname']}.{gc['gc_domain']}"

        watchdog_file = False
        fenced_file = False
        watchdog_time = 0
        fenced_time = 0
        if await middleware.call('failover.licensed'):
            if os.path.exists(WATCHDOG_ALERT_FILE):
                watchdog_file = True
                with open(WATCHDOG_ALERT_FILE, 'rb') as f:
                    watchdog_time = struct.unpack("@i", f.read(4))[0]
            if os.path.exists(FENCED_ALERT_FILE):
                fenced_file = True
                with open(FENCED_ALERT_FILE, 'rb') as f:
                    fenced_time = struct.unpack("@i", f.read(4))[0]

            controller = await middleware.call('failover.node')
            if controller == 'B':
                hostname = f"{gc['gc_hostname_b']}.{gc['gc_domain']}"

        # If the watchdog alert file exists,
        # then we can assume that carp-state-change-hook.py
        # panic'ed the box by design via a watchdog countdown.
        # Let's alert the end user why we did this
        if watchdog_file and (not fenced_file or watchdog_time > fenced_time):
            await middleware.call("alert.oneshot_create", "UnscheduledReboot", textwrap.dedent(f"""\
                {hostname} had a failover event.
                The system was rebooted to ensure a proper failover occurred.
                The operating system successfully came back online at {now}.
            """))

        # If the fenced alert file exists,
        # then we can assume that fenced panic'ed the box by design.
        # Let's alert the end user why we did this
        elif fenced_file:
            await middleware.call("alert.oneshot_create", "UnscheduledReboot", textwrap.dedent(f"""\
                {hostname} had a failover event.
                The system was rebooted because persistent SCSI reservations were lost and/or cleared.
                The operating system successfully came back online at {now}.
            """))

        else:
            await middleware.call("alert.oneshot_create", "UnscheduledReboot", textwrap.dedent(f"""\
                {hostname} had an unscheduled system reboot.
                The operating system successfully came back online at {now}.
            """))

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
