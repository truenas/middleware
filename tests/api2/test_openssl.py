import pytest

import subprocess

from middlewared.test.integration.utils import call, ssh
from auto_config import ha


@pytest.mark.skipif(not ha, reason='Test only valid for HA')
def test_fips_context():
    payload = """midclt call --job system.security.update '{"enable_fips": true}' && openssl list -providers > /root/osslproviders && midclt call --job system.security.update '{"enable_fips": false}'"""
    print("FIPS payload")
    ssh(payload, capture_output=True, check=False)
    print("Were back in!")
    print(ssh("cat /root/opensslproviders"))
