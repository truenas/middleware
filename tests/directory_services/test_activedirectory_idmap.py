import pytest

from contextlib import contextmanager
from middlewared.test.integration.assets import directory_service
from middlewared.test.integration.utils import call


@pytest.fixture(scope="module")
def join_ad():
    with directory_service.directoryservice('ACTIVEDIRECTORY') as ds:
        yield ds


def set_ds_config(config, change_while_disabled=False):
    # Changes to `configuration` key in directory services config requires them to be disabled
    config.pop('id', None)
    if change_while_disabled:
        # Save the change in the call that disables directory services and re-enable them
        # without further changes, as happens when the change is made through a form.
        call('directoryservices.update', config | {'enable': False}, job=True)
        return call('directoryservices.update', {'enable': True}, job=True)

    call('directoryservices.update', {'enable': False}, job=True)
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


@contextmanager
def set_idmap_ad(ds_config, change_while_disabled=False):
    try:
        new_config = ds_config['configuration'] | {'idmap': {
            'builtin': {'range_low': 90000, 'range_high': 100000},
            'idmap_domain': {
                'name': ds_config['configuration']['idmap']['idmap_domain']['name'],
                'idmap_backend': 'AD',
                'range_low': 10000,
                'range_high': 80000,
                'unix_primary_group': True,
                'schema_mode': 'RFC2307',
            }
        }}
        yield set_ds_config(ds_config | {'configuration': new_config}, change_while_disabled)
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
    ([
        {
            'name': 'CANARY1',
            'idmap_backend': 'RID',
            'range_low': 150000001,
            'range_high': 300000000,
        },
    ], r'conflicts with range \[100000001-200000000\]'),  # Overlaps the primary domain
    ([
        {
            'name': 'CANARY1',
            'idmap_backend': 'RID',
            'range_low': 100000001,
            'range_high': 200000000,
        },
    ], r'conflicts with range \[100000001-200000000\]'),  # Same range and backend as the primary domain
    ([
        {
            'name': 'CANARY1',
            'idmap_backend': 'RID',
            'range_low': 95000000,
            'range_high': 99000000,
        },
    ], r'conflicts with range \[90000001-100000000\] for BUILTIN'),
    ([
        {
            'name': 'CANARY1',
            'idmap_backend': 'RID',
            'range_low': 200000001,
            'range_high': 300000000,
        },
        {
            'name': 'canary1',
            'idmap_backend': 'RID',
            'range_low': 300000001,
            'range_high': 400000000,
        },
    ], 'Domain name canary1 is already used by trusted domain CANARY1'),
))
def test_trusted_domain_configuration(join_ad, trusted_doms, error):
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


def test_trusted_domain_uses_primary_domain_name(join_ad):
    name = join_ad['config']['configuration']['idmap']['idmap_domain']['name']
    trusted_dom = {'name': name, 'idmap_backend': 'RID', 'range_low': 200000001, 'range_high': 300000000}
    with pytest.raises(Exception, match='is already used by the primary domain'):
        with update_trusted_domains(join_ad['config'], [trusted_dom]):
            pass


def test_trusted_domain_uses_name_reported_by_domain_controller(join_ad):
    """
    The primary domain's name may be unset when the configuration is saved. It is replaced by the name that the domain
    controller reports when directory services are enabled, so the collision can only be detected at that point.
    """
    config = join_ad['config']
    idmap = config['configuration']['idmap']
    name = idmap['idmap_domain']['name']
    new_config = config['configuration'] | {
        'idmap': idmap | {'idmap_domain': idmap['idmap_domain'] | {'name': None}},
        'enable_trusted_domains': True,
        'trusted_domains': [{'name': name, 'idmap_backend': 'RID', 'range_low': 200000001, 'range_high': 300000000}],
    }
    try:
        with pytest.raises(Exception, match='is already used by the primary domain'):
            set_ds_config(config | {'configuration': new_config}, change_while_disabled=True)
    finally:
        set_ds_config(config)


def test_idmap_ad(join_ad):
    with set_idmap_ad(join_ad['config']) as config:
        # uid + gid should now be offset from RID value by 10K (based on how we provisioned IDs
        # on the test server)
        user_obj = call('user.get_user_obj', {'username': join_ad['account'].user_obj['pw_name'], 'sid_info': True})
        rid = int(user_obj['sid'].split('-')[-1])
        assert user_obj['pw_uid'] == rid + 10000
        assert user_obj['pw_gid'] == 10513  # RID 513 + 10000 (offset)


def test_idmap_change_saved_while_disabled(join_ad):
    """
    The user and group cache must be rebuilt when the idmap change is saved in the call that disables
    directory services, which leaves nothing to compare against when they are re-enabled.
    """
    username = join_ad['account'].user_obj['pw_name']

    # Make sure the account is cached under the current idmap configuration
    cached = call('user.query', [['username', '=', username]], {'get': True})
    assert cached['uid'] == join_ad['account'].user_obj['pw_uid']

    with set_idmap_ad(join_ad['config'], change_while_disabled=True):
        user_obj = call('user.get_user_obj', {'username': username, 'sid_info': True})
        assert user_obj['pw_uid'] == int(user_obj['sid'].split('-')[-1]) + 10000

        cached = call('user.query', [['username', '=', username]], {'get': True})
        assert cached['uid'] == user_obj['pw_uid']
