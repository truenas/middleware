import datetime
import os
import textwrap

from middlewared.alert.base import AlertCategory, AlertClass, SimpleOneShotAlertClass, AlertLevel

WATCHDOG_ALERT_FILE = "/data/sentinels/.watchdog-alert"
FENCED_ALERT_FILE = "/data/sentinels/.fenced-alert"


class ScheduledRebootAlertClass(AlertClass, SimpleOneShotAlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = "Scheduled System Reboot"
    text = "%s"
    deleted_automatically = False


def get_fqdn(middleware):
    gc = middleware.call_sync("datastore.config", "network.globalconfiguration")
    key = "gc_hostname_a"
    if middleware.call_sync("failover.node") == "B":
        key = "gc_hostname_b"

    return f"{gc[key]}.{gc['gc_domain']}" if gc["gc_domain"] else gc[key]


def get_sentinel_files_time_and_clean_them_up(middleware):
    watchdog_time = fenced_time = None
    try:
        os.makedirs(os.path.dirname(FENCED_ALERT_FILE), exist_ok=True)
    except Exception:
        middleware.logger.error('Unhandled exceptin creating sentinels directory', exc_info=True)
    else:
        for idx, i in enumerate((WATCHDOG_ALERT_FILE, FENCED_ALERT_FILE)):
            try:
                with open(i) as f:
                    time = float(f.read().strip())
                    if idx == 0:
                        watchdog_time = time
                    else:
                        fenced_time = time

                # if file exists, we've gotten the time from it so remove it
                os.unlink(i)
            except (FileNotFoundError, ValueError):
                pass

    return watchdog_time, fenced_time


def setup_impl(middleware):
    if not middleware.call_sync("core.is_starting_during_boot") or not middleware.call_sync("failover.licensed"):
        return

    now = datetime.datetime.now().strftime("%c")
    fqdn = get_fqdn(middleware)
    watchdog_time, fenced_time = get_sentinel_files_time_and_clean_them_up(middleware)
    if watchdog_time and (not fenced_time or watchdog_time > fenced_time):
        middleware.call_sync("alert.oneshot_create", "ScheduledReboot", textwrap.dedent(f"""\
            {fqdn} had a failover event.
            The system was rebooted to ensure a proper failover occurred.
            The operating system successfully came back online at {now}.
        """))
    elif fenced_time:
        middleware.call_sync("alert.oneshot_create", "ScheduledReboot", textwrap.dedent(f"""\
            {fqdn} had a failover event.
            The system was rebooted because persistent SCSI reservations were lost and/or cleared.
            The operating system successfully came back online at {now}.
        """))


async def setup(middleware):
    await middleware.run_in_thread(setup_impl, middleware)
