from middlewared.test.integration.utils import call, ha_test


@ha_test
def test_01_verify_fenced_is_running():
    assert call('failover.fenced.run_info')['running']
