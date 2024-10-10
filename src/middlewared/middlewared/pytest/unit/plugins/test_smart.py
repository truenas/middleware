import textwrap
import json

import pytest

from middlewared.plugins.smart import parse_smart_selftest_results, parse_current_smart_selftest
from middlewared.api.current import (
    AtaSelfTest, NvmeSelfTest, ScsiSelfTest
)


def test__parse_smart_selftest_results__ataprint__1():
    data = {
        "power_on_time": {
            "hours": 16590
        },
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
        {
            "num": 0,
            "description": "Short offline",
            "status": "SUCCESS",
            "status_verbose": "Completed without error",
            "remaining": 0.0,
            "lifetime": 16590,
            "lba_of_first_error": None,
            "poh_ago": 0
        },
        {
            "num": 1,
            "description": "Short offline",
            "status": "SUCCESS",
            "status_verbose": "Completed without error",
            "remaining": 0.0,
            "lifetime": 16589,
            "lba_of_first_error": None,
            "poh_ago": 1
        }
    ]


def test__parse_smart_selftest_results__ataprint__2():
    data = {
        "power_on_time": {
            "hours": 16590
        },
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
                        "lifetime_hours": 16590
                    }
                ],
                "error_count_total": 0,
                "error_count_outdated": 0
                }
            }
        }
    assert parse_smart_selftest_results(data) == [
        {
            "num": 0,
            "description": "Offline",
            "status": "RUNNING",
            "status_verbose": "Self-test routine in progress",
            "remaining": 1.0,
            "lifetime": 0,
            "lba_of_first_error": None,
            "poh_ago": 0
        }
    ]


def test__parse_smart_selftest_results__nvmeprint__1():
    assert parse_smart_selftest_results({
        "power_on_time": {
            "hours": 18636
        },
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
        {
            "num": 0,
            "description": "Short",
            "status": "SUCCESS",
            "status_verbose": "Completed without error",
            "power_on_hours": 18636,
            "failing_lba": None,
            "nsid": None,
            "seg": None,
            "sct": 0x0,
            "code": 0x0,
            "poh_ago": 0
        },
    ]


def test__parse_smart_selftest_results__scsiprint__1():
    assert parse_smart_selftest_results({
        "power_on_time": {
            "hours": 3943
        },
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
        {
            "num": 0,
            "description": "Background short",
            "status": "FAILED",
            "status_verbose": "Completed, segment failed",
            "segment_number": None,
            "lifetime": 3943,
            "lba_of_first_error": None,
            "poh_ago": 0
        }
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
