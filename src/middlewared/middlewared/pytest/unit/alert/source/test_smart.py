import pytest

from middlewared.alert.source.smart import SMARTAlertSource


# The parse_* methods never touch self.middleware, so a bare instance is enough.
SOURCE = SMARTAlertSource(None)


def _selftest_entry(passed):
    return {
        "type": {"value": 255, "string": "Vendor (0xff)"},
        "status": {
            "value": 0 if passed else 7,
            "string": "Completed without error" if passed else "Completed: read failure",
            "passed": passed,
        },
        "lifetime_hours": 46601,
    }


def _ata_data(self_test_log=None, attributes=None):
    """Build a minimal `smartctl -x -jc` ATA payload."""
    data = {
        "device": {"name": "/dev/sda", "protocol": "ATA"},
        "serial_number": "AAAABBBBCCCCDDDD",
        "ata_smart_attributes": {"table": attributes or []},
    }
    if self_test_log is not None:
        data["ata_smart_self_test_log"] = self_test_log
    return data


# NAS-141215: smartctl nests the self-test table under "extended" or "standard",
# never directly under "ata_smart_self_test_log". Each case below pins down a
# branch of parse_ata_smart_info's self-test handling.
@pytest.mark.parametrize(
    "self_test_log,expected_testfail",
    [
        # Real-world shape from a Micron 5200 (extended log, newest test passed).
        pytest.param(
            {"extended": {"count": 1, "table": [_selftest_entry(True)]}},
            False,
            id="extended-newest-passed",
        ),
        # Newest extended test failed -> alert. The pre-fix code missed this because
        # it looked for a non-existent top-level "table" key.
        pytest.param(
            {"extended": {"count": 1, "table": [_selftest_entry(False)]}},
            True,
            id="extended-newest-failed",
        ),
        # NAS-140419: table[] is newest-first, so a failure in an older entry must
        # NOT alert when the most recent (index 0) test passed.
        pytest.param(
            {"extended": {"count": 2, "table": [_selftest_entry(True), _selftest_entry(False)]}},
            False,
            id="extended-older-failed-ignored",
        ),
        # Fallback path: drives without GP logging emit "standard" instead.
        pytest.param(
            {"standard": {"table": [_selftest_entry(False)]}},
            True,
            id="standard-newest-failed",
        ),
        pytest.param(
            {"standard": {"table": [_selftest_entry(True)]}},
            False,
            id="standard-newest-passed",
        ),
        # No self-test log at all -> no failure.
        pytest.param(None, False, id="missing-log"),
        pytest.param({}, False, id="empty-log"),
        # Regression guard: a (non-smartctl) top-level "table" must be ignored, not
        # read as the self-test log.
        pytest.param({"table": [_selftest_entry(False)]}, False, id="bogus-toplevel-table"),
    ],
)
def test_parse_ata_self_test_failure(self_test_log, expected_testfail):
    info = SOURCE.parse_ata_smart_info(_ata_data(self_test_log=self_test_log))
    assert info.smart_testfail is expected_testfail


def test_parse_ata_attributes():
    """Uncorrected errors (187), spare block reserve (170) and erase count (173)
    are pulled from the SMART attribute table."""
    attributes = [
        {"id": 187, "value": 100, "raw": {"value": 5}},  # Reported_Uncorrect
        {"id": 170, "value": 42, "raw": {"value": 0}},  # Reserved_Block_Pct
        {"id": 173, "value": 100, "raw": {"value": 1234}},  # Avg_Block-Erase_Count
    ]
    info = SOURCE.parse_ata_smart_info(_ata_data(attributes=attributes))
    assert info.uncorrected_errors == 5
    assert info.spare_block_reserve == 42
    assert info.erase_count == 1234


def test_parse_smart_info_routes_ata():
    data = _ata_data(self_test_log={"extended": {"table": [_selftest_entry(False)]}})
    info = SOURCE.parse_smart_info(data)
    assert info.smart_testfail is True
    assert info.unknown_device is False
