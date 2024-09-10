import pytest

from middlewared.test.integration.utils import call


def test_alert_gets():
    call("alertservice.query")
    call("alertservice.list_types")


def test_alertservice():
    data = ["name", "type", "attributes", "level", "enabled"]

    # create
    payload = {
        "name": "Critical Email Test",
        "type": "Mail",
        "attributes": {
            "email": "eric.spam@ixsystems.com"
        },
        "level": "CRITICAL",
        "enabled": True
    }
    results = call("alertservice.create", payload)
    for key in data:
        assert results[key] == payload[key]

    alertservice_id = results['id']

    # update
    payload = {
        "name": "Warning Email Test",
        "type": "Mail",
        "attributes": {
            "email": "william.spam@ixsystems.com@"
        },
        "level": "WARNING",
        "enabled": False
    }
    results = call(f"alertservice.update", alertservice_id, payload)
    for key in data:
        assert results[key] == payload[key]

    # delete
    call("alertservice.delete", alertservice_id)
    assert call("alertservice.query", [["id", "=", alertservice_id]]) == []
