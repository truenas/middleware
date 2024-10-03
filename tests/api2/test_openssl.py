import pytest

from middlewared.test.integration.utils import call, ssh
from auto_config import ha


@pytest.mark.skipif(not ha, reason='Test only valid for HA')
def test_fips_context():
    call('system.security.update', {'enable_fips': True}, job=True)
    print("AIDEN enabled fips")
    reason_1 = call('failover.call_remote', 'system.reboot.list_reasons')
    reason_2 = call('system.reboot.list_reasons')
    fips_test = ssh('openssl list -providers')
    print(fips_test, reason_1, reason_2)
    assert '3.0.9' in fips_test
    call('system.security.update', {'enable_fips': False}, job=True)
    print("AIDEN disabled fips")
    reason_1 = call('failover.call_remote', 'system.reboot.list_reasons')
    reason_2 = call('system.reboot.list_reasons')
    fips_test = ssh('openssl list -providers')
    print(fips_test, reason_1, reason_2)
