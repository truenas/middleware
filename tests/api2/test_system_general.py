from middlewared.test.integration.utils import call

TIMEZONE = "America/New_York"


def test_setting_timezone():
    assert TIMEZONE in call("system.general.timezone_choices")
    call("system.general.update", {"timezone": TIMEZONE})
    assert call("system.general.config")["timezone"] == TIMEZONE
