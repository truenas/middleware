import pytest

from contextlib import contextmanager
from middlewared.test.integration.assets import directory_service
from middlewared.test.integration.assets.product import product_type
from middlewared.test.integration.utils import call


@pytest.fixture(scope="module")
def set_product_type():
    with product_type():
        yield


@pytest.fixture(scope="module")
def join_ad():
    with directory_service.directoryservice('ACTIVEDIRECTORY') as ds:
        yield ds


def set_ds_config(config):
    # Changes to `configuration` key in directory services config requires them to be disabled
    call('directoryservices.update', {'enable': False}, job=True)
    config.pop('id', None)
    return call('directoryservices.update', config, job=True)


def check_idmap_config(trusted_dom):
    # First get basic settings
    prefix = f'idmap config {trusted_dom["name"]} :'
    assert call('smb.getparm', f'{prefix} backend', 'global') == trusted_dom['idmap_backend'].lower()

    idmap_range = call('smb.getparm', f'{prefix} range', 'global')
    assert idmap_range.strip() == f'{trusted_dom["range_low"]} - {trusted_dom["range_high"]}'

    match trusted_dom['idmap_backend']:
        case 'RID':
            pass
        case 'AD':
            upg = call('smb.getparm', f'{prefix} unix_primary_group', 'global').lower()
            assert upg == 'true' if trusted_dom['unix_primary_group'] else 'false'
            assert call('smb.getparm', f'{prefix} schema_mode', 'global') == 'RFC2307'
        case 'LDAP':
            basedn = call('smb.getparm', f'{prefix} ldap_base_dn', 'global')
            assert basedn == trusted_dom['ldap_base_dn']
            userdn = call('smb.getparm', f'{prefix} ldap_user_dn', 'global')
            assert userdn == trusted_dom['ldap_user_dn']
            url = call('smb.getparm', f'{prefix} ldap_url', 'global')
            assert url == trusted_dom['ldap_url']
        case 'RFC2307':
            userdn = call('smb.getparm', f'{prefix} ldap_user_dn', 'global')
            assert userdn == trusted_dom['ldap_user_dn']
            url = call('smb.getparm', f'{prefix} ldap_url', 'global')
            assert url == trusted_dom['ldap_url']
            bpu = call('smb.getparm', f'{prefix} bind_path_user', 'global')
            assert bpu == trusted_dom['bind_path_user']
            bpg = call('smb.getparm', f'{prefix} bind_path_group', 'global')
            assert bpg == trusted_dom['bind_path_group']
            assert call('smb.getparm', f'{prefix} ldap_server', 'global') == 'stand-alone'
        case _:
            raise ValueError(f'{trusted_dom["idmap_backend"]}: unexpected idmap backend')


@contextmanager
def update_trusted_domains(ds_config, trusted_doms):
    try:
        new_config = ds_config['configuration'] | {'enable_trusted_domains': True, 'trusted_domains': trusted_doms}
        yield set_ds_config(ds_config | {'configuration': new_config})
    finally:
        # restore original configuration
        set_ds_config(ds_config)


@pytest.mark.parametrize('trusted_doms, error', (
    ([
        {
            'name': 'CANARY1',
            'idmap_backend': 'RID',
            'range_low': 200000001,
            'range_high': 300000000,
        },
        {
            'name': 'CANARY2',
            'idmap_backend': 'RID',
            'range_low': 300000001,
            'range_high': 400000000,
        },
    ], None),  # Adding multiple non-overlapping RID configurations should succeed
    ([
        {
            'name': 'CANARY1',
            'idmap_backend': 'RID',
            'range_low': 200000001,
            'range_high': 300000000,
        },
        {
            'name': 'CANARY2',
            'idmap_backend': 'RID',
            'range_low': 250000001,
            'range_high': 400000000,
        },
    ], 'conflicts with range for'),
    ([
        {
            'name': 'CANARY1',
            'idmap_backend': 'RID',
            'range_low': 200000001,
            'range_high': 300000000,
        },
        {
            'name': 'CANARY2',
            'idmap_backend': 'AD',
            'schema_mode': 'RFC2307',
            'range_low': 1000,
            'range_high': 600000,
            'unix_primary_group': True,
        },
    ], None),
    ([
        {
            'name': 'CANARY1',
            'idmap_backend': 'LDAP',
            'range_low': 1000,
            'range_high': 60000,
            'ldap_base_dn': directory_service.LDAPBASEDN,
            'ldap_user_dn': directory_service.LDAPBINDDN,
            'ldap_user_dn_password': directory_service.LDAPBINDPASSWORD,
            'ldap_url': f'ldaps://{directory_service.LDAPHOSTNAME}',
            'readonly': True,
            'validate_certificates': False,
        },
    ], None),
    ([
        {
            'name': 'CANARY1',
            'idmap_backend': 'RFC2307',
            'range_low': 1000,
            'range_high': 60000,
            'bind_path_user': directory_service.LDAPBASEDN,
            'bind_path_group': directory_service.LDAPBASEDN,
            'ldap_user_dn': directory_service.LDAPBASEDN,
            'ldap_user_dn_password': directory_service.LDAPBINDPASSWORD,
            'ldap_url': f'ldaps://{directory_service.LDAPHOSTNAME}',
            'validate_certificates': False,
        },
    ], None),
))
def test_trusted_domain_configuration(set_product_type, join_ad, trusted_doms, error):
    # Substantive directory services changes require disabling / stopping them
    if error:
        with pytest.raises(Exception, match=error):
            with update_trusted_domains(join_ad['config'], trusted_doms):
                pass
    else:
        with update_trusted_domains(join_ad['config'], trusted_doms) as config:
            # Perform health check to make sure we didn't break winbindd
            call('directoryservices.health.check')

            # make sure config applied to DB properly
            assert len(trusted_doms) == len(config['configuration']['trusted_domains'])
            for idx, dom in enumerate(trusted_doms):
                for key, value in dom.items():
                    assert config['configuration']['trusted_domains'][idx][key] == value

            assert config['configuration']['enable_trusted_domains'] is True

            # Make sure idmap config applied
            for dom in trusted_doms:
                check_idmap_config(dom)
