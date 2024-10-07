import pytest

import subprocess

from middlewared.test.integration.utils import call, ssh
from auto_config import ha


@pytest.mark.skipif(not ha, reason='Test only valid for HA')
def test_fips_version():
    # The reason we have a set of commands in a payload is because of some annoying FIPS technicalities.
    # Basically, when FIPS is enabled, we can't use SSH because the key used by root isn't using a FIPS approved algorithm.
    # To allow testing, we write our FIPS information to a file during this phase, and then go back and disable FIPS to get SSH back.
    payload = """midclt call --job system.security.update '{"enable_fips": true}' && openssl list -providers > /root/osslproviders && midclt call --job system.security.update '{"enable_fips": false}'"""
    print(ssh(payload, complete_response=True, timeout=300))
    assert False, ssh("cat /root/osslproviders")
    assert "3.0.9" in ssh("cat /root/osslproviders")
