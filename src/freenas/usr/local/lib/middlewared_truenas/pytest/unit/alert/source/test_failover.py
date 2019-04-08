# Copyright (c) 2018 iXsystems, Inc.
# All rights reserved.
# This file is a part of TrueNAS
# and may not be copied and/or distributed
# without the express permission of iXsystems.

import pytest

from middlewared.alert.source.failover import check_carp_states


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
def test__check_carp_states(local_masters, local_backups, remote_masters, remote_backups, results):
    assert check_carp_states((local_masters, local_backups), (remote_masters, remote_backups)) == results
