from middlewared.test.integration.utils import call

TIMEZONE = "America/New_York"

def test_system_is_ready_and_sane():
    assert call("system.ready") is True
    assert call("system.info")["version"] == call("system.version")
    assert call("system.product_type") in ("SCALE", "SCALE_ENTERPRISE")


def test_check_system_set_time():
    """
    This test intentionally slews our clock to be off
    by 300 seconds and then verifies that it got set
    """
    results = call("system.info")

    # Convert to seconds
    datetime = results["datetime"]["$date"] / 1000

    # hop 300 seconds into the past
    target = datetime - 300
    call("system.set_time", int(target))

    results = call("system.info")
    datetime2 = results["datetime"]["$date"] / 1000

    # This is a fudge-factor because NTP will start working
    # pretty quickly to correct the slew.
    assert abs(target - datetime2) < 60


def test_setting_timezone():
    assert TIMEZONE in call("system.general.timezone_choices")
    call("system.general.update", {"timezone": TIMEZONE})
    assert call("system.general.config")["timezone"] == TIMEZONE
