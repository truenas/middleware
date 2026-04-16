from middlewared.alert.source.ipmi_sel import (
    remove_deasserted_records,
    remove_orphaned_assertions,
)

import pytest


@pytest.mark.parametrize("records,result", [
    (
        [
            {
                "name": "PS2 Status",
                "event_direction": "Assertion Event",
                "event": "Power Supply Failure detected"
            },
            {
                "name": "PS2 Status",
                "event_direction": "Deassertion Event",
                "event": "Power Supply Failure detected"
            },
            {
                "name": "Sensor #255",
                "event_direction": "Assertion Event",
                "event": "Event Offset = 00h"
            },
        ],
        [2],
    )
])
def test_remove_deasserted_records(records, result):
    assert remove_deasserted_records(records) == [records[i] for i in result]


FAN5_NONCRITICAL = {
    "name": "SYS_FAN5",
    "type": "Fan",
    "event_direction": "Assertion Event",
    "event": "Lower Non-critical - going low ; Sensor Reading = 0.00 RPM ; Threshold = 300.00 RPM",
}
FAN5_CRITICAL = {
    "name": "SYS_FAN5",
    "type": "Fan",
    "event_direction": "Assertion Event",
    "event": "Lower Critical - going low ; Sensor Reading = 0.00 RPM ; Threshold = 150.00 RPM",
}
CPU_TEMP_WARNING = {
    "name": "CPU0_TEMP",
    "type": "Temperature",
    "event_direction": "Assertion Event",
    "event": "Upper Non-critical - going high",
}
PSU_FAILURE = {
    "name": "PS2 Status",
    "type": "Power Supply",
    "event_direction": "Assertion Event",
    "event": "Power Supply Failure detected",
}
FAN_DEASSERT = {
    "name": "SYS_FAN5",
    "type": "Fan",
    "event_direction": "Deassertion Event",
    "event": "Lower Critical - going low",
}


@pytest.mark.parametrize("records,sensor_states,expected", [
    # BMC missed the deassertion (controller was unplugged during fan
    # replacement): fan is Nominal now, drop both stale assertions.
    (
        [FAN5_NONCRITICAL, FAN5_CRITICAL],
        {"SYS_FAN5": "Nominal"},
        [],
    ),
    # Fan is still in a bad state — keep the assertion.
    (
        [FAN5_NONCRITICAL],
        {"SYS_FAN5": "Critical"},
        [FAN5_NONCRITICAL],
    ),
    # Unknown sensor state — be conservative and keep the assertion.
    (
        [FAN5_NONCRITICAL],
        {},
        [FAN5_NONCRITICAL],
    ),
    # Non-threshold sensor (discrete PSU) in Nominal state must be kept;
    # "Nominal" doesn't imply a past PSU failure assertion is stale.
    (
        [PSU_FAILURE],
        {"PS2 Status": "Nominal"},
        [PSU_FAILURE],
    ),
    # Deassertion records are left alone regardless of sensor state.
    (
        [FAN_DEASSERT],
        {"SYS_FAN5": "Nominal"},
        [FAN_DEASSERT],
    ),
    # Mixed: suppress the Nominal threshold assertion, keep others.
    (
        [FAN5_NONCRITICAL, CPU_TEMP_WARNING, PSU_FAILURE],
        {"SYS_FAN5": "Nominal", "CPU0_TEMP": "Warning", "PS2 Status": "Nominal"},
        [CPU_TEMP_WARNING, PSU_FAILURE],
    ),
])
def test_remove_orphaned_assertions(records, sensor_states, expected):
    assert remove_orphaned_assertions(records, sensor_states) == expected
