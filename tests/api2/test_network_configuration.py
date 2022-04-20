import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)

import pytest

from middlewared.test.integration.utils import call, ssh
from auto_config import dev_test

# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')
NEW_HOSTNAME = 'dummy123'


def test_changing_hostname():
    current_hostname = call('network.configuration.config')['hostname']

    call('network.configuration.update', {'hostname': NEW_HOSTNAME})
    assert ssh('hostname').strip() == NEW_HOSTNAME

    call('network.configuration.update', {'hostname': current_hostname})
    assert ssh('hostname').strip() == current_hostname
