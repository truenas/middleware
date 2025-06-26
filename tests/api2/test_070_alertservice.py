from middlewared.test.integration.utils import call, client


def test_alert_gets():
    call("alertservice.query")


def test_alertservice():
    data = ["name", "attributes", "level", "enabled"]

    # create
    payload = {
        "name": "Critical Email Test",
        "attributes": {
            "type": "Mail",
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
        "attributes": {
            "type": "Mail",
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


def test_alertservice_2504():
    with client(version="v25.04.0") as c:
        c.call("alertservice.query")

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
        results = c.call("alertservice.create", payload)
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
        results = c.call(f"alertservice.update", alertservice_id, payload)
        for key in data:
            assert results[key] == payload[key]

        # delete
        c.call("alertservice.delete", alertservice_id)
        assert c.call("alertservice.query", [["id", "=", alertservice_id]]) == []
