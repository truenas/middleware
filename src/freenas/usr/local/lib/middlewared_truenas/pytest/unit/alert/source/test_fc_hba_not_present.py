# Copyright (c) 2018 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

from mock import Mock, patch

from middlewared.alert.source.fc_hba_not_present import FCHBANotPresentAlertSource

PORTLIST = """<ctlportlist>
<targ_port id="131">
    <frontend_type>camtgt</frontend_type>
    <port_name>isp0</port_name>
    <physical_port>0</physical_port>
    <virtual_port>0</virtual_port>
</targ_port>
<targ_port id="132">
    <frontend_type>camtgt</frontend_type>
    <port_name>isp1</port_name>
    <physical_port>1</physical_port>
    <virtual_port>0</virtual_port>
</targ_port>
<targ_port id="133">
    <frontend_type>camtgt</frontend_type>
    <port_name>isp1</port_name>
    <physical_port>2</physical_port>
    <virtual_port>3</virtual_port>
</targ_port>
</ctlportlist>"""


def test__ok():
    middleware = Mock()
    middleware.call_sync.return_value = [
        {
            "id": 2, "fc_port": "isp0", "fc_target": {
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


def test__ok_physical_port():
    middleware = Mock()
    middleware.call_sync.return_value = [
        {
            "id": 2, "fc_port": "isp1/1", "fc_target": {
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


def test__ok_physical_port_virtual_port():
    middleware = Mock()
    middleware.call_sync.return_value = [
        {
            "id": 2, "fc_port": "isp1/2/3", "fc_target": {
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
