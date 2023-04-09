import os
import sys
import time
sys.path.append(os.getcwd())
from auto_config import ha

from middlewared.test.integration.utils import client

# Only read the test on HA
if ha:
    def test_apply_and_verify_license():
        with client(host_ip=os.environ.get('controller1_ip', None)) as c:
            with open(os.environ.get('license_file', '/root/license.txt')) as f:
                # apply license
                c.call('system.license_update', f.read())

                # verify license is applied
                assert c.call('failover.licensed') is True

                retries = 30
                sleep_time = 1
                for i in range(retries):
                    if c.call('failover.call_remote', 'failover.licensed') is False:
                        # we call a hook that runs in a background task
                        # so give it a bit to propagate to other controller
                        # furthermore, our VMs are...well...inconsistent to say the least
                        # so sometimes this is almost instant while others I've 10+ secs
                        time.sleep(sleep_time)
                    else:
                        break
                else:
                    assert False, f'Timed out after {sleep_time * retries}s waiting on license to sync to standby'
