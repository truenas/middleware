import pytest
from middlewared.service_exception import CallError
from middlewared.test.integration.utils import call, mock
from middlewared.test.integration.utils.alert import (
    MOCK_ALERT_CLASS,
    get_alerts_by_class,
    wait_for_alerts_by_class,
)


def test_oneshot_delete_invalid_class():
    with pytest.raises(CallError) as ve:
        call("alert.oneshot_delete", "ThisAlertClassDoesNotExist")

    assert "Invalid alert source" in ve.value.errmsg


def test_oneshot_delete_not_a_one_shot_class():
    with pytest.raises(CallError) as ve:
        call("alert.oneshot_delete", "VolumeStatus")

    assert "is not a one-shot alert class" in ve.value.errmsg


def test_oneshot_delete_removes_alert():
    with mock("test.test1", return_value=None):
        assert wait_for_alerts_by_class(MOCK_ALERT_CLASS)

        call("alert.oneshot_delete", [MOCK_ALERT_CLASS])

        assert get_alerts_by_class(MOCK_ALERT_CLASS) == []


def test_oneshot_delete_keeps_alerts_that_do_not_match_the_query():
    with mock("test.test1", return_value=None):
        assert wait_for_alerts_by_class(MOCK_ALERT_CLASS)

        call("alert.oneshot_delete", MOCK_ALERT_CLASS, "this query matches nothing")

        assert get_alerts_by_class(MOCK_ALERT_CLASS)

    call("alert.oneshot_delete", MOCK_ALERT_CLASS)


def test_oneshot_delete_nonexistent_alert_is_not_an_error():
    call("alert.oneshot_delete", MOCK_ALERT_CLASS)
    call("alert.oneshot_delete", MOCK_ALERT_CLASS)
