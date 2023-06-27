from middlewared.alert.source.ipmi_sel import remove_deasserted_records

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
