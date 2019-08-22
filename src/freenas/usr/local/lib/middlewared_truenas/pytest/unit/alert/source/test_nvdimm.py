# Copyright (c) 2019 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

import textwrap

from middlewared.alert.source.nvdimm import produce_nvdimm_alerts


def test__produce_nvdimm_alerts__ok():
    alerts = produce_nvdimm_alerts(
        0,
        textwrap.dedent("""\
            Critical Health Info: 0x0
        """),
        textwrap.dedent("""\
            Module Health: 0x0
            Module Current Temperature: 34 C
            Error Threshold Status: 0x0
            Warning Threshold Status: 0x0
            NVM Lifetime: 100%
            Count of DRAM Uncorrectable ECC Errors: 0
            Count of DRAM Correctable ECC Error Above Threshold Events: 0
        """),
        textwrap.dedent("""\
            ES Lifetime Percentage: 99%
            ES Current Temperature: 23 C
            Total Runtime: 65535
        """),
    )

    assert alerts == []


def test__produce_nvdimm_alerts__PERSISTENCY_RESTORED():
    alerts = produce_nvdimm_alerts(
        0,
        textwrap.dedent("""\
            Critical Health Info: 0x4<PERSISTENCY_RESTORED>
        """),
        textwrap.dedent("""\
            Module Health: 0x0
            Module Current Temperature: 34 C
            Error Threshold Status: 0x0
            Warning Threshold Status: 0x0
            NVM Lifetime: 100%
            Count of DRAM Uncorrectable ECC Errors: 0
            Count of DRAM Correctable ECC Error Above Threshold Events: 0
        """),
        textwrap.dedent("""\
            ES Lifetime Percentage: 99%
            ES Current Temperature: 23 C
            Total Runtime: 65535
        """),
    )

    assert alerts == []


def test__produce_nvdimm_alerts__everything_is_broken():
    alerts = produce_nvdimm_alerts(
        0,
        textwrap.dedent("""\
            Critical Health Info: 0x1
        """),
        textwrap.dedent("""\
            Module Health: 0x900<NOT_ENOUGH_ENERGY_FOR_CSAVE,NO_ES_PRESENT>
            Module Current Temperature: 34 C
            Error Threshold Status: 0x3
            Warning Threshold Status: 0x4
            NVM Lifetime: 15%
            Count of DRAM Uncorrectable ECC Errors: 0
            Count of DRAM Correctable ECC Error Above Threshold Events: 0
        """),
        textwrap.dedent("""\
            ES Lifetime Percentage: 5%
            ES Current Temperature: 0 C
            Total Runtime: 65535
        """),
    )

    assert len(alerts) == 6
    assert alerts[0].title % alerts[0].args == "NVDIMM 0 Critical Health Info is 0x1"
    assert alerts[1].title % alerts[1].args == \
        "NVDIMM 0 Module Health is 0x900: NOT ENOUGH ENERGY FOR CSAVE, NO ES PRESENT"
    assert alerts[2].title % alerts[2].args == "NVDIMM 0 Error Threshold Status is 0x3"
    assert alerts[3].title % alerts[3].args == "NVDIMM 0 Warning Threshold Status is 0x4"
    assert alerts[4].title % alerts[4].args == "NVDIMM 0 NVM Lifetime is 15%"
    assert alerts[4].level.name == "WARNING"
    assert alerts[5].title % alerts[5].args == "NVDIMM 0 ES Lifetime is 5%"
    assert alerts[5].level.name == "CRITICAL"
