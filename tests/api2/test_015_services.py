import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)

import pytest

from truenas_api_client import ClientException
from middlewared.test.integration.utils import call

def test_001_oom_check():
    pid = call('core.get_pid')
    assert call('core.get_oom_score_adj', pid) == -1000


def test_non_silent_service_start_failure():
    """
    Test that starting a service with invalid configuration raises a
    non-empty CallError when silent=False. UPS with no driver configured
    in MASTER mode should fail in check_configuration before starting.
    """
    with pytest.raises(ClientException) as e:
        call('service.control', 'START', 'ups', {'silent': False}, job=True)

    assert e.value.error, 'Error message should not be empty'
    assert 'cannot start' in e.value.error.lower()
