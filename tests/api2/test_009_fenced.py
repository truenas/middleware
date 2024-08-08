import pytest

from auto_config import ha
from middlewared.test.integration.utils import call


@pytest.mark.skipif(not ha, reason='HA only test')
def test_01_verify_fenced_is_running():
    assert call('failover.fenced.run_info')['running']
