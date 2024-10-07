import pytest

import subprocess

from middlewared.test.integration.utils import call, ssh
from auto_config import ha


@pytest.mark.skipif(not ha, reason='Test only valid for HA')
def test_fips_context():
    payload = """midclt call --job system.security.update '{"enable_fips": true}' && openssl list -providers > /root/osslproviders && cat /root/osslproviders && midclt call --job system.security.update '{"enable_fips": false}'"""
    print("FIPS payload")
    print(ssh(payload, complete_response=True, check=False, timeout=300))
    print("Were back in!")
    assert "3.0.9" in ssh("cat /root/osslproviders")
