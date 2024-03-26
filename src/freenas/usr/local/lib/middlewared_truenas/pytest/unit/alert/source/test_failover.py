# Copyright (c) - iXsystems Inc.
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from unittest.mock import Mock

import pytest

from middlewared.plugins.failover import FailoverService


@pytest.mark.parametrize("local_masters,local_backups,remote_masters,remote_backups,results", [
    (["ntb0"], [], [], ["ntb0"], []),
    ([], ["ntb0"], ["ntb0"], [], []),
    (["ntb0"], [], ["ntb0"], [], ["Interface ntb0 is MASTER on both nodes"]),
    ([], ["ntb0"], [], ["ntb0"], ["Interface ntb0 is BACKUP on both nodes"]),
    (["ntb0", "ntb1"], [], [], ["ntb0"], ["Interface ntb1 is not configured for failover on remote system"]),
    (["ntb0"], ["ntb1"], [], ["ntb0"], ["Interface ntb1 is not configured for failover on remote system"]),
    (["ntb0"], [], ["ntb1"], ["ntb0"], ["Interface ntb1 is not configured for failover on local system"]),
    (["ntb0"], [], [], ["ntb0", "ntb1"], ["Interface ntb1 is not configured for failover on local system"]),
])
async def test__check_carp_states(local_masters, local_backups, remote_masters, remote_backups, results):
    assert await FailoverService(Mock()).check_carp_states(
        (local_masters, local_backups), (remote_masters, remote_backups)
    ) == results
