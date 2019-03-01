import textwrap

import pytest

from middlewared.plugins.smart import parse_smart_selftest_results


def test__parse_smart_selftest_results__ataprint__1():
    assert parse_smart_selftest_results(textwrap.dedent("""\
        smartctl 6.6 2017-11-05 r4594 [FreeBSD 11.1-STABLE amd64] (local build)
        Copyright (C) 2002-17, Bruce Allen, Christian Franke, www.smartmontools.org

        === START OF READ SMART DATA SECTION ===
        SMART Self-test log structure revision number 1
        Num  Test_Description    Status                  Remaining  LifeTime(hours)  LBA_of_first_error
        # 1  Short offline       Completed without error       00%     16590         -
        # 2  Short offline       Completed without error       00%     16589         -
    """)) == [
        {
            "num": 1,
            "description": "Short offline",
            "status": "SUCCESS",
            "status_verbose": "Completed without error",
            "remaining": 0.0,
            "lifetime": 16590,
            "lba_of_first_error": None,
        },
        {
            "num": 2,
            "description": "Short offline",
            "status": "SUCCESS",
            "status_verbose": "Completed without error",
            "remaining": 0.0,
            "lifetime": 16589,
            "lba_of_first_error": None,
        }
    ]


@pytest.mark.parametrize("line,subresult", [
    # Longest possible error message
    ("# 1  Extended offline    Completed: servo/seek failure 80%      2941         -", {
        "status": "FAILED",
        "status_verbose": "Completed: servo/seek failure",
        "remaining": 0.8,
    }),
    # Test in progress
    ("# 1  Selective offline   Self-test routine in progress 90%       352         -", {
        "status": "RUNNING",
    })
])
def test__parse_smart_selftest_results__ataprint(line, subresult):
    hdr = "Num  Test_Description    Status                  Remaining  LifeTime(hours)  LBA_of_first_error"
    assert {k: v for k, v in parse_smart_selftest_results(f"{hdr}\n{line}")[0].items() if k in subresult} == subresult


def test__parse_smart_selftest_results__scsiprint__1():
    assert parse_smart_selftest_results(textwrap.dedent("""\
        smartctl version 5.37 [i686-pc-linux-gnu] Copyright (C) 2002-6 Bruce Allen
        Home page is http://smartmontools.sourceforge.net/
        SMART Self-test log
        Num  Test              Status                 segment  LifeTime  LBA_first_err [SK ASC ASQ]
             Description                              number   (hours)
        # 1  Background long   Completed, segment failed   -    3943                 - [-   -    -]
    """)) == [
        {
            "num": 1,
            "description": "Background long",
            "status": "FAILED",
            "status_verbose": "Completed, segment failed",
            "segment_number": None,
            "lifetime": 3943,
            "lba_of_first_error": None,
        },
    ]
