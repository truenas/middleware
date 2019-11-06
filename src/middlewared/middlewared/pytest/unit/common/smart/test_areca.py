import textwrap

from asynctest import CoroutineMock
from mock import Mock, patch
import pytest

from middlewared.common.camcontrol import camcontrol_list
from middlewared.common.smart.areca import annotate_devices_with_areca_dev_id

CAMCONTROL = textwrap.dedent("""\
    scbus0 on ahcich0 bus 0:
    <>                                 at scbus0 target -1 lun ffffffff ()
    scbus1 on ahcich1 bus 0:
    <>                                 at scbus1 target -1 lun ffffffff ()
    scbus2 on ahcich2 bus 0:
    <>                                 at scbus2 target -1 lun ffffffff ()
    scbus3 on ahcich3 bus 0:
    <>                                 at scbus3 target -1 lun ffffffff ()
    scbus4 on ahcich4 bus 0:
    <>                                 at scbus4 target -1 lun ffffffff ()
    scbus5 on ahcich5 bus 0:
    <>                                 at scbus5 target -1 lun ffffffff ()
    scbus6 on ahcich6 bus 0:
    <>                                 at scbus6 target -1 lun ffffffff ()
    scbus7 on ahcich7 bus 0:
    <>                                 at scbus7 target -1 lun ffffffff ()
    scbus8 on ahcich8 bus 0:
    <>                                 at scbus8 target -1 lun ffffffff ()
    scbus9 on ahcich9 bus 0:
    <>                                 at scbus9 target -1 lun ffffffff ()
    scbus10 on ahcich10 bus 0:
    <>                                 at scbus10 target -1 lun ffffffff ()
    scbus11 on ahcich11 bus 0:
    <>                                 at scbus11 target -1 lun ffffffff ()
    scbus12 on ahcich12 bus 0:
    <>                                 at scbus12 target -1 lun ffffffff ()
    scbus13 on ahcich13 bus 0:
    <>                                 at scbus13 target -1 lun ffffffff ()
    scbus14 on arcmsr0 bus 0:
    <TOSHIBA HDWE140 R001>             at scbus14 target 1 lun 0 (pass0,da0)
    <TOSHIBA HDWE140 R001>             at scbus14 target 1 lun 1 (pass1,da1)
    <WDC WD60EFRX-68L0BN1 R001>        at scbus14 target 1 lun 2 (pass2,da2)
    <WDC WD60EFRX-68L0BN1 R001>        at scbus14 target 1 lun 3 (pass3,da3)
    <WDC WD60EFRX-68L0BN1 R001>        at scbus14 target 1 lun 4 (pass4,da4)
    <WDC WD60EFRX-68L0BN1 R001>        at scbus14 target 1 lun 5 (pass5,da5)
    <WDC WD60EFRX-68L0BN1 R001>        at scbus14 target 1 lun 6 (pass6,da6)
    <WDC WD60EFRX-68L0BN1 R001>        at scbus14 target 1 lun 7 (pass7,da7)
    <WDC WD60EFRX-68L0BN1 R001>        at scbus14 target 2 lun 0 (pass8,da8)
    <WDC WD60EFRX-68L0BN1 R001>        at scbus14 target 2 lun 1 (pass9,da9)
    <WDC WD60EFRX-68L0BN1 R001>        at scbus14 target 2 lun 2 (pass10,da10)
    <WDC WD60EFRX-68L0BN1 R001>        at scbus14 target 2 lun 3 (pass11,da11)
    <WDC WD60EFRX-68L0BN1 R001>        at scbus14 target 2 lun 5 (pass12,da12)
    <WDC WD60EFRX-68L0BN1 R001>        at scbus14 target 2 lun 7 (pass13,da13)
    <SanDisk SSD PLUS 12 R001>         at scbus14 target 3 lun 7 (pass14,da14)
    <Areca RAID controller R001>       at scbus14 target 16 lun 0 (pass15)
    <>                                 at scbus14 target -1 lun ffffffff ()
    scbus15 on camsim0 bus 0:
    <>                                 at scbus15 target -1 lun ffffffff ()
    scbus-1 on xpt0 bus 0:
    <>                                 at scbus-1 target -1 lun ffffffff (xpt0)
""")

DISK_INFO = textwrap.dedent("""\
      # Enc# Slot#   ModelName                        Capacity  Usage
    ===============================================================================
      1  01  Slot#1  N.A.                                0.0GB  N.A.
      2  01  Slot#2  N.A.                                0.0GB  N.A.
      3  01  Slot#3  N.A.                                0.0GB  N.A.
      4  01  Slot#4  N.A.                                0.0GB  N.A.
      5  01  Slot#5  N.A.                                0.0GB  N.A.
      6  01  Slot#6  N.A.                                0.0GB  N.A.
      7  01  Slot#7  N.A.                                0.0GB  N.A.
      8  01  Slot#8  N.A.                                0.0GB  N.A.
      9  02  SLOT 01 TOSHIBA HDWE140                  4000.8GB  JBOD
     10  02  SLOT 02 TOSHIBA HDWE140                  4000.8GB  JBOD
     11  02  SLOT 03 WDC WD60EFRX-68L0BN1             6001.2GB  JBOD
     12  02  SLOT 04 WDC WD60EFRX-68L0BN1             6001.2GB  JBOD
     13  02  SLOT 05 WDC WD60EFRX-68L0BN1             6001.2GB  JBOD
     14  02  SLOT 06 WDC WD60EFRX-68L0BN1             6001.2GB  JBOD
     15  02  SLOT 07 WDC WD60EFRX-68L0BN1             6001.2GB  JBOD
     16  02  SLOT 08 WDC WD60EFRX-68L0BN1             6001.2GB  JBOD
     17  02  SLOT 09 WDC WD60EFRX-68L0BN1             6001.2GB  JBOD
     18  02  SLOT 10 WDC WD60EFRX-68L0BN1             6001.2GB  JBOD
     19  02  SLOT 11 WDC WD60EFRX-68L0BN1             6001.2GB  JBOD
     20  02  SLOT 12 WDC WD60EFRX-68L0BN1             6001.2GB  JBOD
     21  02  SLOT 13 N.A.                                0.0GB  N.A.
     22  02  SLOT 14 WDC WD60EFRX-68L0BN1             6001.2GB  JBOD
     23  02  SLOT 15 N.A.                                0.0GB  N.A.
     24  02  SLOT 16 WDC WD60EFRX-68L0BN1             6001.2GB  JBOD
     25  02  SLOT 17 N.A.                                0.0GB  N.A.
     26  02  SLOT 18 N.A.                                0.0GB  N.A.
     27  02  SLOT 19 N.A.                                0.0GB  N.A.
     28  02  SLOT 20 N.A.                                0.0GB  N.A.
     29  02  SLOT 21 N.A.                                0.0GB  N.A.
     30  02  SLOT 22 N.A.                                0.0GB  N.A.
     31  02  SLOT 23 N.A.                                0.0GB  N.A.
     32  02  SLOT 24 SanDisk SSD PLUS 120GB            120.0GB  JBOD
     33  02  EXTP 01 N.A.                                0.0GB  N.A.
     34  02  EXTP 02 N.A.                                0.0GB  N.A.
     35  02  EXTP 03 N.A.                                0.0GB  N.A.
     36  02  EXTP 04 N.A.                                0.0GB  N.A.
    ===============================================================================
    GuiErrMsg<0x00>: Success.
""")

SYS_INFO = textwrap.dedent("""\
    The System Information
    ===========================================
    Main Processor     : 800MHz
    CPU ICache Size    : 32KB
    CPU DCache Size    : 32KB
    CPU SCache Size    : 1024KB
    System Memory      : 1024MB/1333MHz/ECC
    Firmware Version   : V1.56 2019-02-20
    BOOT ROM Version   : V1.56 2019-02-20
    Serial Number      : REDACTED
    Controller Name    : ARC-1882IX-24
    Current IP Address : 0.0.0.0
    ===========================================
    GuiErrMsg<0x00>: Success.
""")


@pytest.mark.asyncio
async def test__annotate_devices_with_areca_enclosure__ok():
    mock = CoroutineMock(return_value=Mock(stdout=CAMCONTROL))
    with patch("middlewared.common.camcontrol.run", mock):
        devices = await camcontrol_list()

    mock = CoroutineMock(side_effect=lambda *args, **kwargs: Mock(stdout={"disk": DISK_INFO, "sys": SYS_INFO}[args[1]]))
    with patch("middlewared.common.smart.areca.logger", mock):
        with patch("middlewared.common.smart.areca.run", mock):
            await annotate_devices_with_areca_dev_id(devices)

    dev_ids = [
        '1/2', '2/2', '3/2', '4/2', '5/2', '6/2', '7/2', '8/2', '9/2', '10/2', '11/2', '12/2', '14/2', '16/2', '24/2'
    ]
    assert all(devices[f"da{i}"]["areca_dev_id"] == dev_ids[i] for i in range(0, 15))


@pytest.mark.asyncio
async def test__annotate_devices_with_areca_enclosure__old_firmware():
    mock = CoroutineMock(return_value=Mock(stdout=CAMCONTROL))
    with patch("middlewared.common.camcontrol.run", mock):
        devices = await camcontrol_list()

    OLD_INFO = SYS_INFO.replace("V1.56 2019-02-20", "V1.49 2012-02-20")
    mock = CoroutineMock(side_effect=lambda *args, **kwargs: Mock(stdout={"disk": DISK_INFO, "sys": OLD_INFO}[args[1]]))
    with patch("middlewared.common.smart.areca.logger", mock):
        with patch("middlewared.common.smart.areca.run", mock):
            await annotate_devices_with_areca_dev_id(devices)

    assert all(isinstance(devices[f"da{i}"]["areca_dev_id"], int) for i in range(0, 15))
