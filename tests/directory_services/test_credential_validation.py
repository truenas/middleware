import pytest

from middlewared.test.integration.assets import directory_service


@pytest.mark.parametrize('service_type,credential,config,error', (
    (
        'ACTIVEDIRECTORY',
        {
            'credential_type': 'LDAP_PLAIN',
            'binddn': directory_service.LDAPBINDDN,
            'bindpw': directory_service.LDAPBINDPASSWORD
        },
        None,
        'LDAP authentication methods are only supported for the LDAP service type.'
    ),
    (
        'ACTIVEDIRECTORY',
        {
            'credential_type': 'KERBEROS_USER',
            'username': 'canary',
            'password': 'canary'
        },
        None,
        'The specified credentials were not found on the remote domain controller.'
    ),
    (
        'ACTIVEDIRECTORY',
        {
            'credential_type': 'KERBEROS_PRINCIPAL',
            'principal': 'canary@foo'
        },
        None,
        'Specified kerberos principal does not exist on the TrueNAS server.'
    ),
    (
        'ACTIVEDIRECTORY',
        {
            'credential_type': 'KERBEROS_USER',
            'username': directory_service.AD_DOM2_USERNAME,
            'password': 'canary'
        },
        None,
        'Bind password is incorrect.'
    ),
    (
        'LDAP',
        {
            'credential_type': 'LDAP_PLAIN',
            'binddn': directory_service.LDAPBINDDN,
            'bindpw': 'canary'
        },
        None,
        'LDAP server responded that the specified credentials are invalid.'
    ),
    (
        'LDAP',
        {
            'credential_type': 'LDAP_PLAIN',
            'binddn': directory_service.LDAPBINDDN,
            'bindpw': 'canary'
        },
        {'basedn': directory_service.FREEIPA_BASEDN},  # feed basedn from different server
        'LDAP server responded that the specified credentials are invalid.'
    ),
    (
        'LDAP',
        {
            'credential_type': 'LDAP_PLAIN',
            'binddn': directory_service.LDAPBINDDN,
            'bindpw': directory_service.LDAPBINDPASSWORD,
        },
        {'validate_certificates': True},  # This server is using self-signed cert. Force error 
        'unresolvable, unresponsive or if there is a lower level cryptographic error'
    ),
))
def test_check_credential(service_type, credential, config, error):
    with pytest.raises(Exception, match=error):
        with directory_service.directoryservice(service_type, configuration=config, credential=credential):
            pass
