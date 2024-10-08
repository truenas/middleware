import pytest

import subprocess

from middlewared.test.integration.utils import call, ssh
from auto_config import ha

retry = 5


# Sometimes this test fails because the testing environment has broken failover (randomly. Fun transient error. Reports a failed heartbeat).
@pytest.mark.skipif(not ha, reason='Test only valid for HA')
def test_fips_version():
    # The reason we have a set of commands in a payload is because of some annoying FIPS technicalities.
    # Basically, when FIPS is enabled, we can't use SSH because the SSH key used by root isn't using a FIPS provided algorithm.
    # To allow testing, we write our FIPS information to a file during this phase, and then go disable FIPS to get SSH back all in one joint command.
    payload = """midclt call --job system.security.update '{"enable_fips": true}' && openssl list -providers > /root/osslproviders && midclt call system.reboot.info >> /root/osslproviders && midclt call --job system.security.update '{"enable_fips": false}'"""
    for i in range(retry):
        request = ssh(payload, complete_response=True, check=False, timeout=300)
        if request["returncode"] != 0:
            continue
        break
    else:
        request = ssh(payload, complete_response=True, timeout=300)
        assert False, f"Failed to run FIPS payload after {retry} retries."

    enabled_info = ssh("cat /root/osslproviders")
    # Check that things are what we expect when fips was enabled
    assert "3.0.9" in enabled_info
    assert "FIPS configuration was changed." in enabled_info

    # Check that we no longer have FIPS enabled
    assert "3.0.9" not in ssh("openssl list -providers")
    assert '"reboot_required_reasons": []' in ssh("midclt call system.reboot.info")
