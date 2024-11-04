import pytest

from middlewared.utils.directoryservices.ipa import ldap_dn_to_realm


@pytest.mark.parametrize('ldap_dn,realm', [
    ('dc=company,dc=com', 'company.com'),
    ('dc=tn,dc=ixsystems,dc=net', 'tn.ixsystems.net'),
])
def test_dn_to_realm(ldap_dn, realm):
    assert ldap_dn_to_realm(ldap_dn) == realm
