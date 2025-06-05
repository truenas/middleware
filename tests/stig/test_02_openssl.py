import pytest

from middlewared.test.integration.utils import call, ssh
from auto_config import ha

pytestmark = pytest.mark.skip('100% fail. Needs to be reworked.')

retry = 5
fips_version = "3.0.9"


# Sometimes this test fails because the testing environment has broken failover (randomly. Fun transient error. Reports a failed heartbeat).
@pytest.mark.flaky(reruns=retry, reruns_delay=5)
@pytest.mark.skipif(not ha, reason='Test only valid for HA')
def test_fips_version():
    # The reason we have a set of commands in a payload is because of some annoying FIPS technicalities.
    # Basically, when FIPS is enabled, we can't use SSH because the SSH key used by root isn't using a FIPS provided algorithm. (this might need to be investigated further)
    # To allow testing, we write our FIPS information to a file during this phase, and then go disable FIPS to get SSH back all in one joint command.
    payload = """midclt call --job system.security.update '{"enable_fips": true}' && openssl list -providers > /root/osslproviders && midclt call system.reboot.info >> /root/osslproviders && midclt call --job system.security.update '{"enable_fips": false}'"""

    ssh(payload, complete_response=True, timeout=300)

    # Check that things are what we expect when FIPS was enabled
    enabled_info = ssh("cat /root/osslproviders")
    assert fips_version in enabled_info
    assert "FIPS configuration was changed." in enabled_info

    # Check that we no longer have FIPS enabled
    assert fips_version not in ssh("openssl list -providers")
    assert call("system.reboot.info")["reboot_required_reasons"] == []
