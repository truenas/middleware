# Copyright (c) 2018 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

import asyncio
from datetime import datetime
import textwrap

from mock import Mock, patch

from middlewared.alert.source.fc_hba_not_present import FCHBANotPresentAlertSource

PORTLIST = """<ctlportlist>
<targ_port id="131">
	<port_name>isp0</port_name>
</targ_port>
<targ_port id="132">
	<port_name>isp1</port_name>
</targ_port>
</ctlportlist>"""


def test__ok():
    middleware = Mock()
    middleware.call_sync.return_value = [
        {
            "id": 2, "fc_port": "isp1", "fc_target": {
                "id": 1,
                "iscsi_target_name": "fctarget",
                "iscsi_target_alias": None,
                "iscsi_target_mode": "fc"
            }
        }
    ]

    source = FCHBANotPresentAlertSource(middleware)

    with patch("middlewared.alert.source.fc_hba_not_present.subprocess.check_output") as check_output:
        check_output.return_value = PORTLIST

        assert source.check_sync() == []


def test__not_ok():
    middleware = Mock()
    middleware.call_sync.return_value = [
        {
            "id": 2, "fc_port": "isp2", "fc_target": {
                "id": 1,
                "iscsi_target_name": "fctarget",
                "iscsi_target_alias": None,
                "iscsi_target_mode": "fc"
            }
        }
    ]

    source = FCHBANotPresentAlertSource(middleware)

    with patch("middlewared.alert.source.fc_hba_not_present.subprocess.check_output") as check_output:
        check_output.return_value = PORTLIST

        alerts = source.check_sync()

        assert len(alerts) == 1
        assert alerts[0].args == {
            "port": "isp2",
            "target": "fctarget",
        }
