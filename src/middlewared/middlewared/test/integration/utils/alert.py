import contextlib
from time import sleep

from .call import call
from .mock import mock

# `test.set_mock` creates a `SystemTesting` one-shot alert as a side effect of entering the `mock`
# context manager. It is a `deleted_automatically=False` one-shot alert, which makes it a convenient
# (and cheap) subject for the one-shot/dismiss code paths.
MOCK_ALERT_CLASS = "SystemTesting"
# `system.coredumps` is only ever called by `CoreFilesArePresentAlertSource`, so mocking it only
# affects that single alert source.
COREDUMPS_SOURCE = "CoreFilesArePresent"
# An alert source that runs on every `alert.process_alerts` and that no test interferes with, so its
# statistics can be used to tell whether the alert sources actually ran.
PROBE_SOURCE = "ScrubPaused"


def get_alert_by_id(alert_id):
    return next(filter(lambda alert: alert["id"] == alert_id, call("alert.list")), None)


def get_alerts_by_class(klass):
    return [alert for alert in call("alert.list") if alert["klass"] == klass]


def wait_for_alerts_by_class(klass):
    """`alert.oneshot_create` is a queued job, so its alert does not appear instantly."""
    for _ in range(30):
        if alerts := get_alerts_by_class(klass):
            return alerts
        sleep(1)

    return []


def source_run_count():
    return call("alert.sources_stats").get(PROBE_SOURCE, {}).get("total_count", 0)


def submit_alerts_run():
    """Submit a single `alert.process_alerts` run and wait for it to complete."""
    call("core.bulk", "alert.process_alerts", [[]], job=True)


def run_alerts(fresh=False):
    """Run `alert.process_alerts` to completion, ensuring that the alert sources really did run.

    `alert.process_alerts` also runs periodically and only keeps a single queued job, so a
    submission made while another one is already in flight is silently discarded. Retry until the
    source statistics show that the sources actually ran.

    A run that was already in flight when this function was called captured the system state from
    before the caller installed its mocks. Pass `fresh` to wait for one more complete run, which is
    therefore guaranteed to have started after the mocks became visible.
    """
    target = source_run_count() + (2 if fresh else 1)
    for _ in range(15):
        submit_alerts_run()
        if source_run_count() >= target:
            return

        sleep(1)

    raise AssertionError("alert.process_alerts did not run the alert sources")


def process_alerts():
    call("alert.initialize")
    submit_alerts_run()


def remove_oneshot_alerts(*klasses):
    """Delete every alert of the given one-shot classes and wait for them to be gone.

    An alert class that does not declare `keys` is matched by its whole args, so each of its alerts
    has to be deleted by the args it carries; passing no query at all would only ever match the
    classes that have no args. `alert.oneshot_delete` is a queued job on top of that, so the alerts
    do not disappear immediately either.
    """
    for klass in klasses:
        for alert in get_alerts_by_class(klass):
            call("alert.oneshot_delete", klass, alert["args"])

    for _ in range(30):
        if not any(get_alerts_by_class(klass) for klass in klasses):
            return
        sleep(1)

    raise AssertionError(f"{klasses} alerts were not removed")


@contextlib.contextmanager
def mock_alert():
    """Yield a `SystemTesting` alert, created as a side effect of installing a mock."""
    with mock("test.test1", return_value=None):
        alerts = wait_for_alerts_by_class(MOCK_ALERT_CLASS)
        assert alerts, "test.set_mock did not create a SystemTesting alert"
        yield alerts[0]

    call("alert.oneshot_delete", MOCK_ALERT_CLASS)


@contextlib.contextmanager
def alert_classes(classes):
    try:
        yield call("alertclasses.update", {"classes": classes})
    finally:
        call("alertclasses.update", {"classes": {}})


@contextlib.contextmanager
def alert_service(**kwargs):
    svc = call("alertservice.create", {
        "name": "Coverage Test Alert Service",
        "attributes": {"type": "Slack", "url": "https://127.0.0.1:1/nonexistent"},
        "level": "INFO",
        "enabled": True,
        **kwargs,
    })
    try:
        yield svc
    finally:
        call("alertservice.delete", svc["id"])


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


def wait_for_share_locked_alert(share_type, share_id):
    for _ in range(30):
        if alert := find_share_locked_alert(share_type, share_id):
            return alert
        sleep(1)
    return None


def wait_for_share_locked_alert_cleared(share_type, share_id):
    for _ in range(30):
        if find_share_locked_alert(share_type, share_id) is None:
            return True
        sleep(1)
    return False
