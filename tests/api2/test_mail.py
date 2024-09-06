from middlewared.test.integration.utils import call


def test_config_settings():
    payload = {
        "fromemail": "william.spam@ixsystems.com",
        "outgoingserver": "mail.ixsystems.com",
        "pass": "changeme",
        "port": 25,
        "security": "PLAIN",
        "smtp": True,
        "user": "william.spam@ixsystems.com"
    }
    call("mail.update", payload)
    config = call("mail.config")
    # test that payload is a subset of config
    assert payload.items() <= config.items()
