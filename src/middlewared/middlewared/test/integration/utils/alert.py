from time import sleep

from .call import call


def get_alerts_by_class(klass):
    return [alert for alert in call("alert.list") if alert["klass"] == klass]


def wait_for_alerts_by_class(klass):
    """`alert.oneshot_create` is a queued job, so its alert does not appear instantly."""
    for _ in range(30):
        if alerts := get_alerts_by_class(klass):
            return alerts
        sleep(1)

    return []


def wait_for_alerts_by_class_cleared(klass):
    """`alert.oneshot_delete` is a queued job, so its alert does not disappear instantly.

    The job also shares the `process_alerts` lock, so it waits for a periodic alert run that is
    already in flight.
    """
    for _ in range(30):
        if not get_alerts_by_class(klass):
            return True
        sleep(1)

    return False


def process_alerts():
    call("alert.initialize")
    call("core.bulk", "alert.process_alerts", [[]], job=True)


def find_share_locked_alert(share_type, share_id):
    """Return the ShareLocked alert for the given share, or None.

    `share_type` is the share task type (e.g. 'SMB', 'NFS')."""
    for alert in call('alert.list'):
        if (
            alert['klass'] == 'ShareLocked'
            and alert['args'].get('type') == share_type
            and alert['args'].get('id') == share_id
        ):
            return alert
    return None


def wait_for_share_locked_alert(share_type, share_id, timeout=30):
    for _ in range(timeout):
        if alert := find_share_locked_alert(share_type, share_id):
            return alert
        sleep(1)
    return None


def wait_for_share_locked_alert_cleared(share_type, share_id, timeout=30):
    for _ in range(timeout):
        if find_share_locked_alert(share_type, share_id) is None:
            return True
        sleep(1)
    return False
