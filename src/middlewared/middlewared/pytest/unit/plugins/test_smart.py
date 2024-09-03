import textwrap
import json

import pytest

from middlewared.plugins.smart import parse_smart_selftest_results, parse_current_smart_selftest


def test__parse_smart_selftest_results__ataprint__1():
    data = json.loads(textwrap.dedent("""\
{
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
                        "passed": true
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
                        "passed": true
                    },
                    "lifetime_hours": 16589
                }
            ],
            "error_count_total": 0,
            "error_count_outdated": 0
            }
        }
}
        """))
    assert parse_smart_selftest_results(data) == [
        {
            "num": 0,
            "description": "Short offline",
            "status": "SUCCESS",
            "status_verbose": "Completed without error",
            "remaining": 0.0,
            "lifetime": 16590,
            "lba_of_first_error": None,
        },
        {
            "num": 1,
            "description": "Short offline",
            "status": "SUCCESS",
            "status_verbose": "Completed without error",
            "remaining": 0.0,
            "lifetime": 16589,
            "lba_of_first_error": None,
        }
    ]


def test__parse_smart_selftest_results__ataprint__2():
    data = json.loads("""\
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
                        "remaining_percent": 100,
                        "passed": true
                    },
                    "lifetime_hours": 0
                }
            ],
            "error_count_total": 0,
            "error_count_outdated": 0
            }
        }
}
        """)
    assert parse_smart_selftest_results(data) == [
        {
            "num": 0,
            "description": "Offline",
            "status": "RUNNING",
            "status_verbose": "Self-test routine in progress",
            "remaining": 1.0,
            "lifetime": 0,
            "lba_of_first_error": None,
        },
    ]


def test__parse_smart_selftest_results__nvmeprint__1():
    assert parse_smart_selftest_results(json.loads("""\
{
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
}
    """)) == [
        {
            "num": 0,
            "description": "Short",
            "status": "SUCCESS",
            "status_verbose": "Completed without error",
            "power_on_hours": 18636,
            "failing_lba": None,
            "nsid": None,
            "seg": None,
            "sct": "0x0",
            "code": "0x00",
        },
    ]


def test__parse_smart_selftest_results__scsiprint__1():
    assert parse_smart_selftest_results(json.loads("""\
{
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
}
    """)) == [
        {
            "num": 0,
            "description": "Background short",
            "status": "FAILED",
            "status_verbose": "Completed, segment failed",
            "segment_number": None,
            "lifetime": 3943,
            "lba_of_first_error": None,
        },
    ]


@pytest.mark.parametrize("stdout,result", [
    # ataprint.cpp
    (
        textwrap.dedent("""\
            === START OF READ SMART DATA SECTION ===
            Self-test execution status:        41% of test remaining
            SMART Self-test log
        """),
        {"progress": 59},
    ),
    # nvmeprint.cpp
    (
        textwrap.dedent("""\
            Self-test Log (NVMe Log 0x06)
            Self-test status: Short self-test in progress (3% completed)
            No Self-tests Logged
        """),
        {"progress": 3},
    ),
    # scsiprint.spp
    (
        textwrap.dedent("""\
            Self-test execution status:      (   0)	The previous self-test routine completed
                                             without error or no self-test has ever
                                             been run.

        """),
        None,
    ),
    (
        textwrap.dedent("""\
            Self-test execution status:      ( 242)	Self-test routine in progress...
                                                    20% of test remaining.
        """),
        {"progress": 80},
    ),
    (
        textwrap.dedent("""\
            SMART Self-test log
            Num  Test              Status                 segment  LifeTime  LBA_first_err [SK ASC ASQ]
                 Description                              number   (hours)
            # 1  Background short  Self test in progress ...   -     NOW                 - [-   -    -]
        """),
        {"progress": 0},
    )
])
def test__parse_current_smart_selftest(stdout, result):
    assert parse_current_smart_selftest(stdout) == result
