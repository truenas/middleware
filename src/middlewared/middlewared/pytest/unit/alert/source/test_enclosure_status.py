import copy
from unittest.mock import Mock

import pytest

from middlewared.alert.source.enclosure_status import (
    EnclosureHealthyAlertClass,
    EnclosureStatusAlertSource,
    EnclosureUnhealthyAlertClass,
)
from middlewared.pytest.unit.middleware import Middleware


def make_enclosure(name, enc_id, extra_elements=None):
    """Build a minimal enclosure dict for enclosure2.query."""
    elements = {"Array Device Slot": {}}
    if extra_elements:
        elements.update(extra_elements)
    return {
        "name": name,
        "id": enc_id,
        "model": "",
        "elements": elements,
    }


HEALTHY_COOLING = {
    "Cooling": {
        "Fan1": {
            "descriptor": "Fan1",
            "status": "OK",
            "value": "SpeedRPM=21760.0",
            "value_raw": 0,
        },
    },
}

BAD_COOLING = {
    "Cooling": {
        "Fan1": {
            "descriptor": "Fan1",
            "status": "Critical",
            "value": "SpeedRPM=0",
            "value_raw": 0,
        },
    },
}


@pytest.mark.asyncio
async def test__enc_all_healthy_single():
    """Single healthy enclosure produces one healthy alert."""
    enc = make_enclosure("EncA", "id-a", HEALTHY_COOLING)
    m = Middleware()
    m["enclosure2.query"] = Mock(return_value=[enc])

    source = EnclosureStatusAlertSource(m)
    alerts = await source.check()

    assert len(alerts) == 1
    assert alerts[0].klass == EnclosureHealthyAlertClass
    assert alerts[0].args == ["EncA (id: id-a)"]


@pytest.mark.asyncio
async def test__enc_bad_element_removes_correct_enclosure_from_healthy():
    """When enclosure A has a bad element and enclosure B is healthy,
    only enclosure B should get a healthy alert.

    This test exposes the bug where line 99 uses the stale loop variable
    ``enc_title`` (bound to the last enclosure) instead of
    ``current_bad_element.enc_title``.  With the bug, enclosure B (the
    last enclosure) is incorrectly removed from ``good_enclosures``
    while enclosure A stays, producing a spurious healthy alert for A
    and a missing healthy alert for B.
    """
    enc_a = make_enclosure("EncA", "id-a", BAD_COOLING)
    enc_b = make_enclosure("EncB", "id-b", HEALTHY_COOLING)

    m = Middleware()
    # check() mutates elements (pops "Array Device Slot"), so return
    # fresh copies on every call.
    m["enclosure2.query"] = lambda: copy.deepcopy([enc_a, enc_b])

    source = EnclosureStatusAlertSource(m)

    enc_a_title = "EncA (id: id-a)"
    enc_b_title = "EncB (id: id-b)"

    # Run the checker 5 times so the bad element count reaches the
    # threshold (count >= 5) that triggers the unhealthy alert path.
    for _ in range(4):
        await source.check()
    alerts = await source.check()

    healthy_args = [a.args for a in alerts if a.klass == EnclosureHealthyAlertClass]
    unhealthy_alerts = [a for a in alerts if a.klass == EnclosureUnhealthyAlertClass]

    # Enclosure A has a critical element -> must NOT be marked healthy
    assert [enc_a_title] not in healthy_args, (
        f"Enclosure A should not be healthy but got healthy alerts: {healthy_args}"
    )

    # Enclosure B is fine -> must be marked healthy
    assert [enc_b_title] in healthy_args, (
        f"Enclosure B should be healthy but got healthy alerts: {healthy_args}"
    )

    # There should be exactly one unhealthy alert for enclosure A's fan
    assert len(unhealthy_alerts) == 1
    assert unhealthy_alerts[0].args == ["EncA", "Fan1", "Critical", "SpeedRPM=0", 0]


@pytest.mark.asyncio
async def test__enc_bad_element_under_threshold_all_healthy():
    """Bad elements seen fewer than 5 times should not produce unhealthy alerts."""
    enc_a = make_enclosure("EncA", "id-a", BAD_COOLING)
    enc_b = make_enclosure("EncB", "id-b", HEALTHY_COOLING)

    m = Middleware()
    m["enclosure2.query"] = lambda: copy.deepcopy([enc_a, enc_b])

    source = EnclosureStatusAlertSource(m)
    # First probe – count will be 1, under the threshold of 5
    alerts = await source.check()

    healthy_alerts = [a for a in alerts if a.klass == EnclosureHealthyAlertClass]
    unhealthy_alerts = [a for a in alerts if a.klass == EnclosureUnhealthyAlertClass]

    # Both enclosures should appear healthy (bad element hasn't persisted long enough)
    assert len(healthy_alerts) == 2
    assert len(unhealthy_alerts) == 0
