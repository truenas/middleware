import textwrap
import json

import pytest

from middlewared.plugins.smart import parse_smart_selftest_results, parse_current_smart_selftest
from middlewared.api.current import (
    AtaSelfTest, NvmeSelfTest, ScsiSelfTest
)


def test__parse_smart_selftest_results__ataprint__1():
    data = {
    "ata_smart_self_test_log": {
        "standard": {
            "revision": 1,
            "table": [
                {
                    "type": {
                        "value": 1,
                        "string": "Short offline"
                    },
                    "status": {
                        "value": 0,
                        "string": "Completed without error",
                        "passed": True
                    },
                    "lifetime_hours": 16590
                },
                {
                    "type": {
                        "value": 1,
                        "string": "Short offline"
                    },
                    "status": {
                        "value": 0,
                        "string": "Completed without error",
                        "passed": True
                    },
                    "lifetime_hours": 16589
                }
            ],
            "error_count_total": 0,
            "error_count_outdated": 0
            }
        }
    }
    assert parse_smart_selftest_results(data) == [
        AtaSelfTest(
            0,
            "Short offline",
            "SUCCESS",
            "Completed without error",
            0.0,
            16590,
            None
        ),
        AtaSelfTest(
            1,
            "Short offline",
            "SUCCESS",
            "Completed without error",
            0.0,
            16589,
            None
        )
    ]


def test__parse_smart_selftest_results__ataprint__2():
    data = {
    "ata_smart_self_test_log": {
        "standard": {
            "revision": 1,
            "table": [
                {
                    "type": {
                        "value": 1,
                        "string": "Offline"
                    },
                    "status": {
                        "value": 249,
                        "string": "Self-test routine in progress",
                        "remaining_percent": 100,
                        "passed": True
                    },
                    "lifetime_hours": 0
                }
            ],
            "error_count_total": 0,
            "error_count_outdated": 0
            }
        }
    }
    assert parse_smart_selftest_results(data) == [
        AtaSelfTest(
            0,
            "Offline",
            "RUNNING",
            "Self-test routine in progress",
            100,
            0,
            None
        )
    ]


def test__parse_smart_selftest_results__nvmeprint__1():
    assert parse_smart_selftest_results({
        "nvme_self_test_log": {
            "table": [
                {
                    "self_test_code": {
                        "string": "Short"
                    },
                    "self_test_result": {
                        "string": "Completed without error"
                    },
                    "power_on_hours": 18636
                }
            ],
            "error_count_total": 0,
            "error_count_outdated": 0
        }
    }) == [
        NvmeSelfTest(
            0,
            "Short",
            "SUCCESS",
            "Completed without error",
            18636,
            None,
            None,
            None,
            0x0,
            0x0,
        ),
    ]


def test__parse_smart_selftest_results__scsiprint__1():
    assert parse_smart_selftest_results({
        "scsi_self_test_0": {
            "code": {
                "string": "Background short"
            },
            "result": {
                "string": "Completed, segment failed"
            },
            "power_on_time": {
                "hours": 3943
            }
        }
    }) == [
        ScsiSelfTest(
            0,
            "Background short",
            "FAILED",
            "Completed, segment failed",
            None,
            3943,
            None,
        ),
    ]


@pytest.mark.parametrize("stdout,result", [
    # ataprint.cpp
    (
        {
        "ata_smart_self_test_log": {
            "standard": {
                "revision": 1,
                "table": [
                    {
                        "type": {
                            "value": 1,
                            "string": "Offline"
                        },
                        "status": {
                            "value": 249,
                            "string": "Self-test routine in progress",
                            "remaining_percent": 41,
                            "passed": True
                        },
                        "lifetime_hours": 0
                    }
                ],
                "error_count_total": 0,
                "error_count_outdated": 0
                }
            }
        },
        {"progress": 59},
    ),
    # nvmeprint.cpp
    (
        {
            "nvme_self_test_log": {
                "current_self_test_completion_percent": 3
            }
        },
        {"progress": 3},
    ),
    # scsiprint.spp
    (
        {"junkjson":True},
        None,
    ),
    (
        {"self_test_in_progress":True},
        {"progress": 0}
    )
])
def test__parse_current_smart_selftest(stdout, result):
    assert parse_current_smart_selftest(stdout) == result
