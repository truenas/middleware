from unittest.mock import Mock

import pytest

from middlewared.alert.source.ntp import NTPHealthCheckAlertSource
from middlewared.pytest.unit.middleware import Middleware

UNREACHABLE_PEER = {
    "mode": "SERVER",
    "state": "NOT_SELECTABLE",
    "remote": "192.0.2.1",
    "stratum": 0,
    "poll_interval": 6,
    "reach": 0,
    "lastrx": 0,
    "offset": 0.0,
    "offset_measured": 0.0,
    "jitter": 0.0,
    "active": False,
}
ACTIVE_PEER = UNREACHABLE_PEER | {"state": "BEST", "reach": 255, "active": True}


def nts_source(name, key_length=32, cookies=8):
    return {"name": name, "key_length": key_length, "cookies": cookies, "attempts": 1, "last_success": 60}


async def reason(peers, nts_authdata):
    m = Middleware()
    m["system.time_info"] = Mock(return_value={"uptime_seconds": 600})
    m["system.ntpserver.peers"] = Mock(return_value=peers)
    m.services.system.ntpserver.nts_authdata = nts_authdata

    alert = await NTPHealthCheckAlertSource(m).check()
    return alert.instance.reason if alert else None


@pytest.mark.asyncio
async def test_failing_nts_sources_are_named_sorted_and_once():
    text = await reason(
        [UNREACHABLE_PEER],
        Mock(
            return_value=[
                nts_source("time.example.org", key_length=0, cookies=0),
                nts_source("nts.example.net", cookies=0),
                nts_source("healthy.example.com"),
                nts_source("time.example.org", key_length=0, cookies=0),
            ]
        ),
    )

    assert text.startswith("No Active NTP peers")
    assert ". NTS key establishment is failing for: nts.example.net, time.example.org. Check that TCP port 4460" in text


@pytest.mark.asyncio
async def test_healthy_nts_sources_are_not_blamed():
    text = await reason([UNREACHABLE_PEER], Mock(return_value=[nts_source("time.example.org")]))

    assert text.startswith("No Active NTP peers")
    assert "NTS" not in text


@pytest.mark.asyncio
async def test_failing_to_read_nts_state_does_not_fail_the_source():
    text = await reason([UNREACHABLE_PEER], Mock(side_effect=Exception("chronyc: connection refused")))

    assert text.startswith("No Active NTP peers")
    assert "NTS" not in text


@pytest.mark.asyncio
async def test_nts_state_is_not_read_while_a_peer_is_active():
    nts_authdata = Mock()

    assert await reason([ACTIVE_PEER], nts_authdata) is None
    nts_authdata.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("offset,raised", [(400.0, True), (-400.0, True), (100.0, False), (-100.0, False)])
async def test_offset_beyond_five_minutes_alerts_in_either_direction(offset, raised):
    text = await reason([ACTIVE_PEER | {"offset": offset}], Mock())

    assert (text is not None) is raised
    if raised:
        assert f"has an offset of {offset}" in text
