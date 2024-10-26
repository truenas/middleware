import pytest
from auto_config import ha
from middlewared.test.integration.utils import call, mock

pytestmark = pytest.mark.skipif(not ha, reason='Tests applicable to HA only')

VALID_NODES = ['A', 'B']


def test__mock_remote_node():
    """
    Test that we can mock on the remote node, using direct calls to verify.
    """
    this_node = call('failover.node')
    assert this_node in VALID_NODES
    other_node = call('failover.call_remote', 'failover.node')
    assert other_node in VALID_NODES
    assert this_node != other_node
    with mock('failover.node', return_value='BOGUS1'):
        assert call('failover.node') == 'BOGUS1'
        assert call('failover.call_remote', 'failover.node') == other_node
        with mock('failover.node', return_value='BOGUS2', remote=True):
            assert call('failover.node') == 'BOGUS1'
            assert call('failover.call_remote', 'failover.node') == 'BOGUS2'
        assert call('failover.node') == 'BOGUS1'
        assert call('failover.call_remote', 'failover.node') == other_node
    assert call('failover.node') == this_node
    assert call('failover.call_remote', 'failover.node') == other_node


def test__mock_remote_indirect():
    """
    Test that we can mock on the remote node, using indirect calls to verify.
    """
    mmd = call('failover.mismatch_disks')
    assert mmd['missing_local'] == []
    assert mmd['missing_remote'] == []
    disks = call('failover.get_disks_local')
    with mock('failover.get_disks_local', return_value=disks[1:], remote=True):
        mmd = call('failover.mismatch_disks')
        assert mmd['missing_local'] == []
        assert mmd['missing_remote'] == [disks[0]]
    mmd = call('failover.mismatch_disks')
    assert mmd['missing_local'] == []
    assert mmd['missing_remote'] == []
