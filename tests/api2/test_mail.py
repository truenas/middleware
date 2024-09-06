from middlewared.test.integration.utils import call


def test_config_settings():
    orig_config = call("mail.config")
    payload = {
        "fromemail": "william.spam@ixsystems.com",
        "outgoingserver": "mail.ixsystems.com",
        "pass": "changeme",
        "port": 25,
        "security": "PLAIN",
        "smtp": True,
        "user": "william.spam@ixsystems.com"
    }
    try:
        call("mail.update", payload)
        config = call("mail.config")
        # test that payload is a subset of config
        assert payload.items() <= config.items()
    finally:
        call("mail.update", {key: orig_config[key] for key in payload})
        assert call("mail.config") == orig_config
