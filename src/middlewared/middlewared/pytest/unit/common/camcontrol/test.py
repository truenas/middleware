import asyncio
import textwrap

from mock import Mock, patch
import pytest

from middlewared.common.camcontrol import camcontrol_list


@pytest.mark.asyncio
async def test__camcontrol_list__1():
    with patch("middlewared.common.camcontrol.run") as run:
        run.return_value = asyncio.Future()
        run.return_value.set_result(Mock(stdout=textwrap.dedent("""\
            scbus0 on ata0 bus 0:
            <VBOX HARDDISK 1.0>                at scbus0 target 1 lun 0 (ada0,pass0)
            <>                                 at scbus0 target -1 lun ffffffff ()
            scbus1 on ata1 bus 0:
            <VBOX HARDDISK 1.0>                at scbus1 target 0 lun 0 (ada1,pass1)
            <>                                 at scbus1 target -1 lun ffffffff ()
            scbus2 on camsim0 bus 0:
            <>                                 at scbus2 target -1 lun ffffffff ()
            scbus-1 on xpt0 bus 0:
            <>                                 at scbus-1 target -1 lun ffffffff (xpt0)
        """)))

        assert await camcontrol_list() == {
            "ada0": {
                "driver": "ata",
                "controller_id": 0,
                "channel_no": 1,
                "lun_id": 0,
            },
            "ada1": {
                "driver": "ata",
                "controller_id": 1,
                "channel_no": 0,
                "lun_id": 0,
            }
        }
