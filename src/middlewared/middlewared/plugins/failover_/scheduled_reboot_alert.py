# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

import datetime
import os

WATCHDOG_ALERT_FILE = "/data/sentinels/.watchdog-alert"
FENCED_ALERT_FILE = "/data/sentinels/.fenced-alert"


def get_fqdn(middleware):
    gc = middleware.call_sync("datastore.config", "network.globalconfiguration")
    key = "gc_hostname"
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
        middleware.call_sync("alert.oneshot_create", "FailoverReboot", {'fqdn': fqdn, 'now': now})
        middleware.logger.warning('Failover reboot occurred at %d', watchdog_time)
    elif fenced_time:
        middleware.call_sync("alert.oneshot_create", "FencedReboot", {'fqdn': fqdn, 'now': now})
        middleware.logger.warning('Fenced reboot occurred at %d', fenced_time)
    else:
        middleware.call_sync("alert.oneshot_delete", "FencedReboot")
        middleware.call_sync("alert.oneshot_delete", "FailoverReboot")


async def setup(middleware):
    await middleware.run_in_thread(setup_impl, middleware)
