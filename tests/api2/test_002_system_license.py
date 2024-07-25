import os
import time

import pytest

from auto_config import ha, ha_license
from middlewared.test.integration.utils import call


@pytest.mark.skipif(not ha, reason='Test only valid for HA')
def test_apply_and_verify_license():
    if ha_license:
        _license_string = ha_license
    else:
        with open(os.environ.get('license_file', '/root/license.txt')) as f:
            _license_string = f.read()

    # apply license
    call('system.license_update', _license_string)

    # verify license is applied
    assert call('failover.licensed') is True

    retries = 30
    sleep_time = 1
    for i in range(retries):
        if call('failover.call_remote', 'failover.licensed') is False:
            # we call a hook that runs in a background task
            # so give it a bit to propagate to other controller
            time.sleep(sleep_time)
        else:
            break
    else:
        assert False, f'Timed out after {sleep_time * retries}s waiting on license to sync to standby'
