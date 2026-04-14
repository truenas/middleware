import pytest

from middlewared.alert.source.smart import SMARTAlertSource, SmartInfo


# Real smartctl -x -jc output from NAS-140652 (serial redacted). Two passing
# self-tests — this is the exact input that produced the transient false
# "failed a SMART selftest" alert prior to the fix.
REAL_NAS_140652 = {
    "device": {"name": "/dev/nvme0n1", "type": "nvme", "protocol": "NVMe"},
    "model_name": "TEAM TM8FP6256G",
    "firmware_version": "VC2S038E",
    "nvme_self_test_log": {
        "current_self_test_operation": {
            "value": 0,
            "string": "No self-test in progress",
        },
        "table": [
            {
                "self_test_code": {"value": 1, "string": "Short"},
                "self_test_result": {
                    "value": 0,
                    "string": "Completed without error",
                },
                "power_on_hours": 23575,
            },
            {
                "self_test_code": {"value": 2, "string": "Extended"},
                "self_test_result": {
                    "value": 0,
                    "string": "Completed without error",
                },
                "power_on_hours": 23335,
            },
        ],
    },
}


def _entry(value: int) -> dict:
    return {
        "self_test_code": {"value": 1, "string": "Short"},
        "self_test_result": {"value": value, "string": "x"},
        "power_on_hours": 100,
    }


@pytest.mark.parametrize(
    "data,expected_fail",
    [
        # Real data from NAS-140652 — two passes; must not alert.
        (REAL_NAS_140652, False),
        # Sparse trailing garbage scenario that triggered NAS-140652. smartctl
        # emits entries at their hardware index, so a filtered-out middle slot
        # leaves a JSON null. The old code took [-1] and grabbed the trailing
        # garbage (value=5 = fatal error). The fix iterates past nulls and takes
        # the actual newest entry at [0] (a passing test).
        (
            {"nvme_self_test_log": {"table": [_entry(0), _entry(0), None, _entry(5)]}},
            False,
        ),
        # Genuine failures at index 0 — must still alert for all three NVMe
        # failure codes (5 = fatal error, 6 = unknown failed segment,
        # 7 = known failed segments).
        ({"nvme_self_test_log": {"table": [_entry(5)]}}, True),
        ({"nvme_self_test_log": {"table": [_entry(6)]}}, True),
        ({"nvme_self_test_log": {"table": [_entry(7)]}}, True),
        # Pass at [0] with an old failure behind it — failures age out; only the
        # most recent test's result drives the alert.
        ({"nvme_self_test_log": {"table": [_entry(0), _entry(5)]}}, False),
        # NVMe abort codes (1-4, 8, 9) are not failures — must not alert.
        ({"nvme_self_test_log": {"table": [_entry(1)]}}, False),
        ({"nvme_self_test_log": {"table": [_entry(2)]}}, False),
        ({"nvme_self_test_log": {"table": [_entry(8)]}}, False),
        ({"nvme_self_test_log": {"table": [_entry(9)]}}, False),
        # Reserved "entry not used" sentinel (0xF) — smartctl normally filters
        # these, but if one slips through it must not alert.
        ({"nvme_self_test_log": {"table": [_entry(0xF)]}}, False),
        # Empty table — no exception (old code raised IndexError on table[-1]).
        ({"nvme_self_test_log": {"table": []}}, False),
        # Missing "table" key.
        ({"nvme_self_test_log": {}}, False),
        # Missing "nvme_self_test_log" key entirely.
        ({}, False),
        # Leading null followed by a real passing entry.
        ({"nvme_self_test_log": {"table": [None, _entry(0)]}}, False),
        # current_self_test_operation non-zero (test currently running) — the
        # sibling field must not interfere with reading the table.
        (
            {
                "nvme_self_test_log": {
                    "current_self_test_operation": {"value": 1, "string": "Short"},
                    "table": [_entry(0)],
                }
            },
            False,
        ),
    ],
)
def test_parse_nvme_smart_info(data, expected_fail):
    # parse_nvme_smart_info does not reference self; call it unbound.
    info = SMARTAlertSource.parse_nvme_smart_info(None, data)
    assert isinstance(info, SmartInfo)
    assert info.smart_testfail is expected_fail
