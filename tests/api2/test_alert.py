import errno
import json
import uuid
from datetime import datetime
from time import sleep

import pytest
from middlewared.service_exception import CallError
from middlewared.test.integration.assets.account import user
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, mock, ssh
from middlewared.test.integration.utils.alert import (
    COREDUMPS_SOURCE,
    MOCK_ALERT_CLASS,
    alert_classes,
    alert_service,
    get_alert_by_id,
    get_alerts_by_class,
    mock_alert,
    run_alerts,
    submit_alerts_run,
)

from auto_config import pool_name

ID_PATH = "/dev/disk/by-partuuid/"


def wait_for_alert(timeout=120):
    for _ in range(timeout):
        for alert in call("alert.list"):
            if (
                alert["source"] == "VolumeStatus"
                and alert["args"]["volume"] == pool_name
                and alert["args"]["state"] == "DEGRADED"
            ):
                return alert["id"]
        sleep(1)


@pytest.fixture(scope="module")
def degraded_pool_gptid():
    get_pool = call("pool.query", [["name", "=", pool_name]], {"get": True})
    gptid = get_pool["topology"]["data"][0]["path"].replace(ID_PATH, "")
    ssh(f"zinject -d {gptid} -A fault {pool_name}")
    return gptid


@pytest.fixture(scope="module")
def alert_id(degraded_pool_gptid):
    call("alert.process_alerts")
    result = wait_for_alert()
    if result is None:
        pytest.fail("Timed out while waiting for alert.")
    return result


@pytest.fixture
def db_alert():
    """Yield a callable that stores an arbitrary alert in the database and loads it into memory."""
    created = []

    def make(klass, args, key=None, **changes):
        # Borrow the shape of a stored alert from the `SystemTesting` one the mock creates.
        with mock_alert():
            call("alert.flush_alerts")
            template = call(
                "datastore.query",
                "system.alert",
                [["klass", "=", MOCK_ALERT_CLASS]],
                {"get": True},
            )

        row = dict(
            template,
            klass=klass,
            args=args,
            key=json.dumps(key),
            source="",
            uuid=str(uuid.uuid4()),
            **changes,
        )
        del row["id"]
        call("datastore.insert", "system.alert", row)
        created.append(row["uuid"])

        call("alert.initialize")
        return row["uuid"]

    try:
        yield make
    finally:
        # `alert.flush_alerts` rewrites the whole table, so the rows must be deleted by `uuid`.
        call("datastore.delete", "system.alert", [["uuid", "in", created]])
        call("alert.initialize")
        call("alert.flush_alerts")
        run_alerts()


def test_verify_the_pool_is_degraded(degraded_pool_gptid):
    status = call("zpool.status", {"name": pool_name})
    disk_status = status["pools"][pool_name]["data"][ID_PATH + degraded_pool_gptid]["disk_status"]
    assert disk_status == "DEGRADED"


def test_dismiss_alert(alert_id):
    call("alert.dismiss", alert_id)
    alert = get_alert_by_id(alert_id)
    assert alert["dismissed"] is True, alert


def test_restore_alert(alert_id):
    call("alert.restore", alert_id)
    alert = get_alert_by_id(alert_id)
    assert alert["dismissed"] is False, alert


def test_blocked_alert_source_keeps_its_alerts(alert_id):
    """A blocked source is not re-run, and the alerts it already produced are preserved."""
    lock = call("alert.block_source", "VolumeStatus")
    try:
        run_alerts()
        assert get_alert_by_id(alert_id) is not None
    finally:
        call("alert.unblock_source", lock)


def test_expired_alert_source_lock_is_released(alert_id):
    call("alert.block_source", "VolumeStatus", 0)
    run_alerts()
    assert call("alert.sources_stats")["VolumeStatus"]["total_count"] > 0


def test_clear_the_pool_degradation(degraded_pool_gptid):
    ssh(f"zpool clear {pool_name}")
    status = call("zpool.status", {"name": pool_name})
    disk_status = status["pools"][pool_name]["data"][ID_PATH + degraded_pool_gptid]["disk_status"]
    assert disk_status != "DEGRADED"


@pytest.mark.timeout(120)
def test_wait_for_the_alert_to_disappear(alert_id):
    call("alert.process_alerts")
    while get_alert_by_id(alert_id) is not None:
        sleep(1)


# ---------------------------------------------------------------------------
# alert.list_policies / alert.list_categories
# ---------------------------------------------------------------------------


def test_list_policies():
    assert call("alert.list_policies")


def test_list_categories():
    assert call("alert.list_categories")


def test_list_categories_include_hidden_classes():
    def class_ids(options):
        return {klass["id"] for category in call("alert.list_categories", options) for klass in category["classes"]}

    # `TestAlert` and `AlertSourceRunFailedAlert` are `exclude_from_list=True`.
    assert "Test" not in class_ids({})
    assert "Test" in class_ids({"include_hidden_classes": True})


def test_list_categories_include_all_products():
    def class_ids(options):
        return {klass["id"] for category in call("alert.list_categories", options) for klass in category["classes"]}

    default = class_ids({})
    all_products = class_ids({"include_all_products": True})
    assert default < all_products, "No ENTERPRISE-only alert classes were filtered out"


# ---------------------------------------------------------------------------
# alert.dismiss / alert.restore
# ---------------------------------------------------------------------------


def test_dismiss_nonexistent_alert():
    assert call("alert.dismiss", str(uuid.uuid4())) is None


def test_restore_nonexistent_alert():
    assert call("alert.restore", str(uuid.uuid4())) is None


def test_dismiss_deletes_one_shot_alert_that_is_not_deleted_automatically():
    with mock_alert() as alert:
        assert alert["one_shot"] is True

        call("alert.dismiss", alert["id"])

        assert get_alert_by_id(alert["id"]) is None


def test_restore_alert_hidden_by_never_policy():
    with mock_alert() as alert:
        with alert_classes({MOCK_ALERT_CLASS: {"policy": "NEVER"}}):
            # The alert is filtered out of `alert.list`...
            assert get_alerts_by_class(MOCK_ALERT_CLASS) == []
            # ...and restoring it does not emit an `alert.list` event either.
            assert call("alert.restore", alert["id"]) is None

        assert get_alerts_by_class(MOCK_ALERT_CLASS)


def ipmi_sel_alert(db_alert, dt_iso, **changes):
    args = {
        "name": "Coverage Test Sensor",
        "event_direction": "Assertion",
        "event": "Coverage test",
        "dt_iso": dt_iso,
    }
    key = [args[k] for k in ("name", "event_direction", "event", "dt_iso")]
    return db_alert("IPMISEL", args, key=key, datetime=datetime.fromisoformat(dt_iso), **changes)


def test_dismiss_dismissable_alert(db_alert):
    """`DismissableAlertClass.dismiss` decides which of the related alerts survive.

    `IPMISELAlert.dismiss` dismisses everything up to and including the dismissed alert, so a more
    recent event of the same class remains.
    """
    old = ipmi_sel_alert(db_alert, "2020-01-01T00:00:00")
    new = ipmi_sel_alert(db_alert, "2020-01-02T00:00:00")
    try:
        call("alert.dismiss", old)

        assert get_alert_by_id(old) is None
        assert get_alert_by_id(new) is not None
    finally:
        call("keyvalue.delete", "alert:ipmi_sel:dismissed_datetime")


# ---------------------------------------------------------------------------
# alert source management
# ---------------------------------------------------------------------------


def test_run_source():
    with mock("system.coredumps", return_value=[]):
        assert call("alert.run_source", COREDUMPS_SOURCE) == []


def test_run_source_that_fails():
    with mock("system.coredumps", exception="Coverage test failure"):
        alerts = call("alert.run_source", COREDUMPS_SOURCE)
        assert [alert["klass"] for alert in alerts] == ["AlertSourceRunFailed"]
        assert alerts[0]["args"]["source_name"] == COREDUMPS_SOURCE

        # The error is only logged once, subsequent runs take the "already reported" path.
        call("alert.run_source", COREDUMPS_SOURCE)

    # And the error state is cleared once the source recovers.
    with mock("system.coredumps", return_value=[]):
        assert call("alert.run_source", COREDUMPS_SOURCE) == []


def test_run_source_that_is_unavailable():
    declaration = """\
        async def mock(self):
            from middlewared.alert.base import UnavailableException
            raise UnavailableException()
    """
    with mock("system.coredumps", declaration=declaration):
        with pytest.raises(CallError) as ve:
            call("alert.run_source", COREDUMPS_SOURCE)

        assert ve.value.errno == CallError.EALERTCHECKERUNAVAILABLE

        # `alert.process_alerts` swallows the same exception instead of failing the whole run.
        run_alerts()


def test_block_and_unblock_source():
    lock = call("alert.block_source", COREDUMPS_SOURCE)
    assert lock
    call("alert.unblock_source", lock)
    # Unblocking an already released lock is a no-op.
    call("alert.unblock_source", lock)


def test_block_invalid_source():
    with pytest.raises(CallError) as ve:
        call("alert.block_source", "ThisAlertSourceDoesNotExist")

    assert "Invalid alert source" in ve.value.errmsg


def test_alert_source_clear_run():
    assert call("alert.alert_source_clear_run", COREDUMPS_SOURCE) is None


def test_alert_source_clear_run_invalid_source():
    with pytest.raises(CallError) as ve:
        call("alert.alert_source_clear_run", "ThisAlertSourceDoesNotExist")

    assert ve.value.errno == errno.ENOENT


def test_sources_stats():
    stats = call("alert.sources_stats")
    assert stats

    for name, stat in stats.items():
        assert set(stat) == {"avg", "last", "max", "total_count", "total_time"}, name
        if stat["total_count"]:
            assert stat["avg"] == pytest.approx(stat["total_time"] / stat["total_count"])
        else:
            assert stat["avg"] == 0


# ---------------------------------------------------------------------------
# alert dispatching to alert services
# ---------------------------------------------------------------------------


def test_alert_service_send_failure_is_logged_and_swallowed():
    """A broken alert service must not break `alert.send_alerts`."""
    call("alert.oneshot_delete", MOCK_ALERT_CLASS)

    with alert_service(), mock_alert():
        # Nothing changed since the alert was created, so there is nothing left to send.
        call("core.bulk", "alert.send_alerts", [[]], job=True)

    assert call("alert.list") is not None


def test_alerts_below_the_alert_service_level_are_not_dispatched():
    call("alert.oneshot_delete", MOCK_ALERT_CLASS)

    with (
        alert_service(level="EMERGENCY"),
        alert_classes({MOCK_ALERT_CLASS: {"level": "INFO"}}),
        mock("test.test1", return_value=None),
    ):
        pass

    call("alert.oneshot_delete", MOCK_ALERT_CLASS)


def test_alerts_with_never_policy_are_not_dispatched():
    call("alert.oneshot_delete", MOCK_ALERT_CLASS)

    with (
        alert_service(level="INFO"),
        alert_classes({MOCK_ALERT_CLASS: {"policy": "NEVER"}}),
        mock("test.test1", return_value=None),
    ):
        assert get_alerts_by_class(MOCK_ALERT_CLASS) == []

    call("alert.oneshot_delete", MOCK_ALERT_CLASS)


def test_alerts_for_other_product_types_are_not_dispatched():
    call("alert.oneshot_delete", MOCK_ALERT_CLASS)

    # Entering the inner mock creates a `SystemTesting` alert, which is dispatched to the alert
    # service while the product type does not match any alert class.
    with (
        alert_service(),
        mock("alert.product_type", return_value="COVERAGE_TEST_PRODUCT"),
    ):
        assert call("alert.list") == []

    call("alert.oneshot_delete", MOCK_ALERT_CLASS)


def test_dismissed_alerts_are_not_dispatched(db_alert):
    """A dismissed alert is not included in the alert service payload."""
    call("alert.oneshot_delete", MOCK_ALERT_CLASS)
    dismissed_uuid = db_alert("DeprecatedService", {"service": "coverage"}, key="coverage")
    call("alert.dismiss", dismissed_uuid)
    assert get_alert_by_id(dismissed_uuid)["dismissed"] is True

    with alert_service(), mock("test.test1", return_value=None):
        pass

    call("alert.oneshot_delete", MOCK_ALERT_CLASS)


#: `mail.send` runs on the server, so the messages it is given are recorded there.
MAIL_FILE = "/tmp/coverage_alert_mail"

# `MailSendMessage` leaves its unset fields as a sentinel that only a plain `model_dump` knows how
# to drop, so the message cannot be dumped in JSON mode.
RECORD_MAIL = f"""\
    async def mock(self, job, message, config=None):
        import json
        with open("{MAIL_FILE}", "a") as f:
            f.write(json.dumps(message.model_dump(), default=str) + "\\n")
"""

QUOTA_SOURCE = "Quota"


def sent_mail():
    """The `mail.send` messages the mock recorded, oldest first."""
    return [json.loads(line) for line in ssh(f"cat {MAIL_FILE} 2>/dev/null || true").splitlines() if line]


def quota_alerts(ds):
    return [
        alert
        for alert in call("alert.list")
        if alert["klass"] in ["QuotaWarning", "QuotaCritical"] and (alert["args"] or {}).get("dataset") == ds
    ]


def wait_for_quota_alerts(ds, present, attempts=6):
    """Run the quota alert source until its alert has appeared (or disappeared) again."""
    for _ in range(attempts):
        # The source is only due once an hour, so it has to be made due again by hand.
        call("alert.alert_source_clear_run", QUOTA_SOURCE)
        run_alerts(fresh=True)
        if bool(alerts := quota_alerts(ds)) == present:
            return alerts

    raise AssertionError(f"The quota alert for {ds} did not {'appear' if present else 'disappear'}")


def test_new_alerts_carrying_a_mail_message_send_it():
    """An alert may carry an extra `mail.send` payload that is sent when it is first seen.

    `QuotaAlertSource` attaches one whenever the dataset that ran out of space belongs to a user
    that has an e-mail address, which is the only way an alert comes to carry a message.
    """
    ssh(f"rm -f {MAIL_FILE}")
    ds = f"{pool_name}/alert_quota_test"

    try:
        with (
            mock("mail.send", declaration=RECORD_MAIL),
            user(
                {
                    "username": "quotauser",
                    "full_name": "Quota User",
                    "group_create": True,
                    "password": "test1234",
                    "email": "quotauser@ixsystems.com",
                }
            ) as quota_user,
            dataset("alert_quota_test", {"quota": 1024 * 1024 * 1024}),
        ):
            # The alert is only mailed to the owner of the dataset...
            ssh(f"chown {quota_user['uid']} /mnt/{ds}")
            # ...and only once it has used up more than the 80% warning threshold of its quota.
            ssh(f"dd if=/dev/urandom of=/mnt/{ds}/blob bs=1M count=900")

            (alert,) = wait_for_quota_alerts(ds, True)
            assert alert["klass"] == "QuotaWarning"

            (message,) = sent_mail()
            assert message["to"] == ["quotauser@ixsystems.com"]
            assert message["subject"] == f"{call('system.hostname')}: Quota exceeded on dataset {ds}"
            assert message["text"] == alert["formatted"]
    finally:
        # The dataset is gone, but its alert lives on until the source runs again.
        wait_for_quota_alerts(ds, False)


def test_removal_of_a_hidden_alert_does_not_emit_an_event():
    call("alert.oneshot_delete", MOCK_ALERT_CLASS)

    with alert_classes({MOCK_ALERT_CLASS: {"policy": "NEVER"}}):
        with mock("test.test1", return_value=None):
            pass

        call("alert.oneshot_delete", MOCK_ALERT_CLASS)


# ---------------------------------------------------------------------------
# alert processing gates
# ---------------------------------------------------------------------------


def test_alerts_are_not_processed_until_the_system_is_ready():
    with mock("system.state", return_value="BOOTING"):
        submit_alerts_run()
        call("core.bulk", "alert.send_alerts", [[]], job=True)

    # The system is `READY` again, so alert processing resumes.
    call("alert.oneshot_delete", MOCK_ALERT_CLASS)
    run_alerts()


def test_alerts_collected_while_shutting_down_are_discarded():
    """If the system stops being `READY` while the sources run, their results are thrown away.

    `alert.product_type` is the first thing `run_alerts` does, so mocking it is a reliable way to
    make `system.state` change exactly once the alert sources are about to run.
    """
    product_type = """\
        async def mock(self):
            self.middleware._coverage_shutting_down = True
            return await self.middleware.call("system.product_type")
    """
    system_state = """\
        async def mock(self):
            if getattr(self.middleware, "_coverage_shutting_down", False):
                del self.middleware._coverage_shutting_down
                return "SHUTTING_DOWN"

            return "READY"
    """
    with (
        mock("alert.product_type", declaration=product_type),
        mock("system.state", declaration=system_state),
    ):
        run_alerts(fresh=True)

    call("alert.oneshot_delete", MOCK_ALERT_CLASS)
    run_alerts()
