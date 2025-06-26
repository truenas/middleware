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
        'The remote domain controller does not have the specified credentials.'
    ),
    (
        'ACTIVEDIRECTORY',
        {
            'credential_type': 'KERBEROS_PRINCIPAL',
            'principal': 'canary@foo'
        },
        None,
        'The TrueNAS server does not have the specified Kerberos principal.'
    ),
    (
        'ACTIVEDIRECTORY',
        {
            'credential_type': 'KERBEROS_USER',
            'username': directory_service.AD_DOM2_USERNAME,
            'password': 'canary'
        },
        None,
        'The bind password is not correct.'
    ),
    (
        'LDAP',
        {
            'credential_type': 'LDAP_PLAIN',
            'binddn': directory_service.LDAPBINDDN,
            'bindpw': 'canary'
        },
        None,
        'The LDAP server responded that the specified credentials are invalid.'
    ),
    (
        'LDAP',
        {
            'credential_type': 'LDAP_PLAIN',
            'binddn': directory_service.LDAPBINDDN,
            'bindpw': 'canary'
        },
        {'basedn': directory_service.FREEIPA_BASEDN},  # feed basedn from different server
        'The LDAP server responded that the specified credentials are invalid.'
    ),
    (
        'LDAP',
        {
            'credential_type': 'LDAP_PLAIN',
            'binddn': directory_service.LDAPBINDDN,
            'bindpw': directory_service.LDAPBINDPASSWORD,
        },
        {'validate_certificates': True},  # This server is using self-signed cert. Force error
        'hostname cannot be resolved, the server does not respond'
    ),
))
def test_check_credential(service_type, credential, config, error):
    with pytest.raises(Exception, match=error):
        with directory_service.directoryservice(service_type, configuration=config, credential=credential):
            pass
