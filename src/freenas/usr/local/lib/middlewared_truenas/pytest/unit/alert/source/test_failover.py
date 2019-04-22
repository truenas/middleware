# Copyright (c) 2018 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

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
