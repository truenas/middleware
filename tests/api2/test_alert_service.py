import contextlib

import pytest
from middlewared.service_exception import InstanceNotFound
from middlewared.test.integration.utils import call, client, mock


def test_alert_gets():
    call("alertservice.query")


def test_alertservice():
    data = ["name", "attributes", "level", "enabled"]

    # create
    payload = {
        "name": "Critical Email Test",
        "attributes": {"type": "Mail", "email": "eric.spam@ixsystems.com"},
        "level": "CRITICAL",
        "enabled": True,
    }
    results = call("alertservice.create", payload)
    for key in data:
        assert results[key] == payload[key]

    alertservice_id = results["id"]

    # update
    payload = {
        "name": "Warning Email Test",
        "attributes": {"type": "Mail", "email": "william.spam@ixsystems.com@"},
        "level": "WARNING",
        "enabled": False,
    }
    results = call("alertservice.update", alertservice_id, payload)
    for key in data:
        assert results[key] == payload[key]

    # delete
    call("alertservice.delete", alertservice_id)
    assert call("alertservice.query", [["id", "=", alertservice_id]]) == []


def test_alertservice_2504():
    with client(version="v25.04.0") as c:
        c.call("alertservice.query")

        data = ["name", "type", "attributes", "level", "enabled"]

        # create
        payload = {
            "name": "Critical Email Test",
            "type": "Mail",
            "attributes": {"email": "eric.spam@ixsystems.com"},
            "level": "CRITICAL",
            "enabled": True,
        }
        results = c.call("alertservice.create", payload)
        for key in data:
            assert results[key] == payload[key]

        alertservice_id = results["id"]

        # update
        payload = {
            "name": "Warning Email Test",
            "type": "Mail",
            "attributes": {"email": "william.spam@ixsystems.com@"},
            "level": "WARNING",
            "enabled": False,
        }
        results = c.call("alertservice.update", alertservice_id, payload)
        for key in data:
            assert results[key] == payload[key]

        # delete
        c.call("alertservice.delete", alertservice_id)
        assert c.call("alertservice.query", [["id", "=", alertservice_id]]) == []


def test_alertservice_update_nonexistent():
    with pytest.raises(InstanceNotFound):
        call(
            "alertservice.update",
            1234567,
            {
                "name": "Nonexistent",
                "attributes": {"type": "Mail", "email": "eric.spam@ixsystems.com"},
                "level": "CRITICAL",
            },
        )


def test_alertservice_delete_nonexistent():
    with pytest.raises(InstanceNotFound):
        call("alertservice.delete", 1234567)


def test_alertservice_test_failure():
    """A test alert against an unreachable service reports failure instead of raising."""
    assert (
        call(
            "alertservice.test",
            {
                "name": "Coverage Test Alert Service",
                "attributes": {
                    "type": "Slack",
                    "url": "https://127.0.0.1:1/nonexistent",
                },
                "level": "CRITICAL",
            },
        )
        is False
    )


def test_alertservice_test_success():
    declaration = """\
        async def mock(self, job, message):
            pass
    """
    with mock("mail.send", declaration=declaration):
        assert (
            call(
                "alertservice.test",
                {
                    "name": "Coverage Test Alert Service",
                    "attributes": {"type": "Mail", "email": "eric.spam@ixsystems.com"},
                    "level": "CRITICAL",
                },
            )
            is True
        )


@contextlib.contextmanager
def datastore_alertservice(**kwargs):
    """Create a `system.alertservice` row directly, bypassing API validation."""
    id_ = call(
        "datastore.insert",
        "system.alertservice",
        {
            "name": "Coverage Test Alert Service",
            "type": "Mail",
            "attributes": {"email": "coverage@ixsystems.com"},
            "enabled": False,
            "level": "INFO",
            **kwargs,
        },
    )
    try:
        yield id_
    finally:
        call("datastore.delete", "system.alertservice", [["id", "=", id_]])


def datastore_row(id_):
    return call("datastore.query", "system.alertservice", [["id", "=", id_]])


def test_alertservice_initialize_removes_obsolete_service():
    with datastore_alertservice(type="ThisAlertServiceDoesNotExist") as id_:
        call("alertservice.initialize")

        assert datastore_row(id_) == []


def test_alertservice_initialize_removes_obsolete_attribute():
    attributes = {
        "email": "coverage@ixsystems.com",
        "this_attribute_no_longer_exists": True,
    }
    with datastore_alertservice(attributes=attributes) as id_:
        call("alertservice.initialize")

        assert datastore_row(id_)[0]["attributes"] == {"email": "coverage@ixsystems.com"}


def test_alertservice_initialize_removes_invalid_service():
    with datastore_alertservice(level="ThisLevelDoesNotExist") as id_:
        call("alertservice.initialize")

        assert datastore_row(id_) == []
