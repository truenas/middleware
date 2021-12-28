import textwrap

from asynctest import CoroutineMock, Mock
import pytest

from middlewared.plugins.disk_.smart_attributes import DiskService
from middlewared.pytest.unit.middleware import Middleware


@pytest.mark.asyncio
async def test__disk_service__sata_dom_lifetime_left():

    m = Middleware()
    m["disk.smartctl"] = Mock(return_value=textwrap.dedent("""\
        smartctl 6.6 2017-11-05 r4594 [FreeBSD 11.2-STABLE amd64] (local build)
        Copyright (C) 2002-17, Bruce Allen, Christian Franke, www.smartmontools.org

        === START OF READ SMART DATA SECTION ===
        SMART Attributes Data Structure revision number: 0
        Vendor Specific SMART Attributes with Thresholds:
        ID# ATTRIBUTE_NAME          FLAG     VALUE WORST THRESH TYPE      UPDATED  WHEN_FAILED RAW_VALUE
          9 Power_On_Hours          0x0012   100   100   000    Old_age   Always       -       8693
         12 Power_Cycle_Count       0x0012   100   100   000    Old_age   Always       -       240
        163 Unknown_Attribute       0x0000   100   100   001    Old_age   Offline      -       1065
        164 Unknown_Attribute       0x0000   100   100   001    Old_age   Offline      -       322
        166 Unknown_Attribute       0x0000   100   100   010    Old_age   Offline      -       0
        167 Unknown_Attribute       0x0022   100   100   000    Old_age   Always       -       0
        168 Unknown_Attribute       0x0012   100   100   000    Old_age   Always       -       0
        175 Program_Fail_Count_Chip 0x0013   100   100   010    Pre-fail  Always       -       0
        192 Power-Off_Retract_Count 0x0012   100   100   000    Old_age   Always       -       208
        194 Temperature_Celsius     0x0022   060   060   030    Old_age   Always       -       40 (Min/Max 30/60)
        241 Total_LBAs_Written      0x0032   100   100   000    Old_age   Always       -       14088053817

    """))

    assert abs(await DiskService(m).sata_dom_lifetime_left("ada1") - 0.8926) < 1e-4
