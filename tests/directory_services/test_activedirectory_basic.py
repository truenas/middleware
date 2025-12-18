import os
from time import sleep

import pytest
from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.directory_service import (
    directoryservice, AD_DOM2_LIMITED_USER, AD_DOM2_LIMITED_USER_PASSWORD
)
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.assets.privilege import privilege
from middlewared.test.integration.assets.product import product_type
from middlewared.test.integration.utils import call, client, ssh
from middlewared.test.integration.utils.client import truenas_server
from middlewared.test.integration.utils.system import reset_systemd_svcs, get_gssproxy_state

from auto_config import ha
from protocols import smb_connection, smb_share
from truenas_api_client import ClientException

SMB_NAME = "TestADShare"


def check_ad_started():
    ds = call('directoryservices.status')
    if ds['type'] is None:
        return False

    assert ds['type'] == 'ACTIVEDIRECTORY'
    assert ds['status'] == 'HEALTHY'
    return True


@pytest.fixture(scope="function")
def set_product_type():
    if ha:
        # HA product is already enterprise-licensed
        yield
    else:
        with product_type():
            yield


@pytest.fixture(scope="function")
def enable_ds_auth(set_product_type):
    call("system.general.update", {"ds_auth": True})

    try:
        yield
    finally:
        call("system.general.update", {"ds_auth": False})


@pytest.fixture(scope="function")
def enable_smb():
    call("service.update", "cifs", {"enable": True})
    call("service.control", "START", "cifs", job=True)
    try:
        yield
    finally:
        call("service.update", "cifs", {"enable": False})
        call("service.control", "STOP", "cifs", job=True)


def test_enable_leave_activedirectory():
    reset_systemd_svcs('winbind')
    assert check_ad_started() is False

    if not ha:
        with pytest.raises(ValidationErrors):
            # At this point we are not enterprise licensed
            call("system.general.update", {"ds_auth": True})

    short_name = None

    with directoryservice('ACTIVEDIRECTORY', timeout=15) as ad:
        domain_name = ad['config']['configuration']['domain']
        domain_info = ad['domain_info']
        short_name = domain_info['domain_controller']['pre-win2k_domain']
        netbiosname = call('smb.config')['netbiosname']

        # Make sure we can read our secrets.tdb file
        secrets_has_domain = call('directoryservices.secrets.has_domain', short_name)
        assert secrets_has_domain is True

        # Check that our database has backup of this info written to it.
        db_secrets = call('directoryservices.secrets.get_db_secrets')[f'{netbiosname.upper()}$']
        assert f'SECRETS/MACHINE_PASSWORD/{short_name}' in db_secrets

        # Last password change should be populated
        passwd_change = call('directoryservices.get_last_password_change')
        assert passwd_change['dbconfig'] is not None
        assert passwd_change['secrets'] is not None

        assert check_ad_started() is True

        # Verify that idmapping is working
        pw = ad['account'].user_obj

        # Verify winbindd information
        assert pw['sid'] is not None, str(ad)
        assert not pw['sid'].startswith('S-1-22-1-'), str(ad)
        assert pw['local'] is False
        assert pw['source'] == 'ACTIVEDIRECTORY'

        # DNS updates may not propagate to all nameservers in a timely manner, hence retry a few times.
        retries = 10
        while retries:
            result = call('dnsclient.forward_lookup', {'names': [f'{netbiosname}.{domain_name}']})
            if result:
                break

            retries -= 1
            sleep(1)

        assert len(result) != 0

        addresses = [x['address'] for x in result]
        assert truenas_server.ip in addresses

        res = call('privilege.query', [['name', 'C=', domain_name]], {'get': True})
        assert res['ds_groups'][0]['name'].endswith('domain admins')
        assert res['ds_groups'][0]['sid'].endswith('512')
        assert res['roles'][0] == 'FULL_ADMIN'

        # A few minor validation checks
        with pytest.raises(match='NetBIOS name may not be changed'):
            call('smb.update', {'netbiosname': 'wilbure'})

        with pytest.raises(match='NetBIOS aliases may not be changed'):
            call('smb.update', {'netbiosalias': ['wilbur']})

        with pytest.raises(match='Workgroup may not be changed'):
            call('smb.update', {'workgroup': 'wilbur'})

        # authentication with kerberos requires gssproxy
        assert get_gssproxy_state() == 1

    assert check_ad_started() is False

    secrets_has_domain = call('directoryservices.secrets.has_domain', short_name)
    assert secrets_has_domain is False

    with pytest.raises(KeyError):
        call('user.get_user_obj', {'username': pw['pw_name']})


def test_activedirectory_smb_ops(enable_smb):
    reset_systemd_svcs('winbind')
    with directoryservice('ACTIVEDIRECTORY') as ad:
        domain_info = ad['domain_info']
        short_name = domain_info['domain_controller']['pre-win2k_domain']
        machine_password_key = f'SECRETS/MACHINE_PASSWORD/{short_name}'
        running_pwd = call('directoryservices.secrets.dump')[machine_password_key]
        netbiosname = call('smb.config')['netbiosname']
        db_pwd = call('directoryservices.secrets.get_db_secrets')[f'{netbiosname.upper()}$'][machine_password_key]
        account = ad['account']

        # We've joined and left AD already. Verify secrets still getting backed up correctly.
        assert running_pwd == db_pwd

        with dataset(
            "ad_smb",
            {'share_type': 'SMB'},
            acl=[{
                'tag': 'GROUP',
                'id': account.user_obj['pw_uid'],
                'perms': {'BASIC': 'FULL_CONTROL'},
                'flags': {'BASIC': 'INHERIT'},
                'type': 'ALLOW'
            }]
        ) as ds:
            call('service.control', 'RESTART', 'cifs', job=True)

            with smb_share(f'/mnt/{ds}', {'name': SMB_NAME}):
                with smb_connection(
                    host=truenas_server.ip,
                    share=SMB_NAME,
                    username=account.username,
                    domain=short_name,
                    password=account.password
                ) as c:
                    fd = c.create_file('testfile.txt', 'w')
                    c.write(fd, b'foo')
                    val = c.read(fd, 0, 3)
                    c.close(fd, True)
                    assert val == b'foo'

                    c.mkdir('testdir')
                    fd = c.create_file('testdir/testfile2.txt', 'w')
                    c.write(fd, b'foo2')
                    val = c.read(fd, 0, 4)
                    c.close(fd, True)
                    assert val == b'foo2'

                    c.rmdir('testdir')

        with dataset(
            "ad_datasets",
            {'share_type': 'SMB'},
            acl=[{
                'tag': 'GROUP',
                'id': account.user_obj['pw_uid'],
                'perms': {'BASIC': 'FULL_CONTROL'},
                'flags': {'BASIC': 'INHERIT'},
                'type': 'ALLOW'
            }]
        ) as ds:
            with smb_share(f'/mnt/{ds}', {
                'name': 'DATASETS',
                'purpose': 'LEGACY_SHARE',
                'options': {
                    'auxsmbconf': 'zfs_core:zfs_auto_create = true',
                    'path_suffix': '%D/%U'
                }
            }):
                with smb_connection(
                    host=truenas_server.ip,
                    share='DATASETS',
                    username=account.username,
                    domain=short_name,
                    password=account.password
                ) as c:
                    fd = c.create_file('nested_test_file', "w")
                    c.write(fd, b'EXTERNAL_TEST')
                    c.close(fd)

            acl = call('filesystem.getacl', os.path.join(f'/mnt/{ds}', short_name, account.username), True)
            assert acl['trivial'] is False, str(acl)

        with dataset(
            "ad_home",
            {'share_type': 'SMB'},
            acl=[
                {
                    'tag': 'owner@',
                    'id': None,
                    'perms': {'BASIC': 'FULL_CONTROL'},
                    'flags': {'BASIC': 'INHERIT'},
                    'type': 'ALLOW'
                },
                {
                    'tag': 'GROUP',
                    'id': account.user_obj['pw_uid'],
                    'perms': {'BASIC': 'FULL_CONTROL'},
                    'flags': {'BASIC': 'INHERIT'},
                    'type': 'ALLOW'
                }
            ]
        ) as ds:

            with smb_share(f'/mnt/{ds}', {
                'name': 'TEST_HOME',
                'purpose': 'LEGACY_SHARE',
                'options': {'home': True},
            }):
                # must refresh idmap cache to get new homedir from NSS
                # this means we may need a few seconds for winbindd
                # service to settle down on slow systems (like our CI VMs)
                sleep(10 if ha else 5)

                with smb_connection(
                    host=truenas_server.ip,
                    share='HOMES',
                    username=account.username,
                    domain=short_name,
                    password=account.password
                ) as c:
                    fd = c.create_file('homes_test_file', "w")
                    c.write(fd, b'EXTERNAL_TEST')
                    c.close(fd)

            acl = call('filesystem.getacl', os.path.join(f'/mnt/{ds}', short_name, account.username), True)
            assert acl['trivial'] is False, str(acl)


def test_account_privilege_authentication(enable_ds_auth):
    reset_systemd_svcs('winbind')

    with directoryservice('ACTIVEDIRECTORY') as ds:
        domain_name = ds['config']['configuration']['domain']
        domain_info = ds['domain_info']
        short_name = domain_info['domain_controller']['pre-win2k_domain']

        nusers = call("user.query", [["local", "=", False]], {"count": True})
        assert nusers > 0
        ngroups = call("group.query", [["local", "=", False]], {"count": True})
        assert ngroups > 0

        # RID 513 is constant for "Domain Users"
        domain_sid = call("idmap.domain_info", short_name)['sid']
        with privilege({
            "name": "AD privilege",
            "local_groups": [],
            "ds_groups": [f"{domain_sid}-513"],
            "roles": ["READONLY_ADMIN"],
            "web_shell": False,
        }):
            with client(auth=(f'{AD_DOM2_LIMITED_USER}@{domain_name}', AD_DOM2_LIMITED_USER_PASSWORD)) as c:
                methods = c.call("core.get_methods")
                me = c.call("auth.me")

                assert 'DIRECTORY_SERVICE' in me['account_attributes']
                assert 'ACTIVE_DIRECTORY' in me['account_attributes']

                assert len(c.call("user.query", [["local", "=", False]])) == nusers
                assert len(c.call("group.query", [["local", "=", False]])) == ngroups

            assert "system.info" in methods
            assert "pool.create" not in methods

            # Verify that onetime password for AD users works
            # and that second call fails
            username = ds['account'].user_obj['pw_name']
            otpw = call('auth.generate_onetime_password', {'username': username})
            with client(auth=None) as c:
                resp = c.call('auth.login_ex', {
                    'mechanism': 'PASSWORD_PLAIN',
                    'username': username,
                    'password': otpw
                })

                assert resp['response_type'] == 'SUCCESS'
                assert resp['user_info']['pw_name'] == username

                resp = c.call('auth.login_ex', {
                    'mechanism': 'PASSWORD_PLAIN',
                    'username': username,
                    'password': otpw
                })

                assert resp['response_type'] == 'AUTH_ERR'

            username = f'{ds["account"].username}@{domain_name}'
            with client(auth=(username, ds['account'].password)) as c:
                methods = c.call("core.get_methods")

            assert "pool.create" in methods

            # Alternative formatting for user name <DOMAIN>\<username>.
            # this should also work for auth
            with client(auth=(ds['account'].user_obj['pw_name'], ds['account'].password)) as c:
                methods = c.call("core.get_methods")

            assert "pool.create" in methods


def test_secrets_restore():

    with directoryservice('ACTIVEDIRECTORY', retrieve_user=False):
        reset_systemd_svcs('winbind')
        assert check_ad_started() is True

        ssh('rm /var/db/system/samba4/private/secrets.tdb')

        with pytest.raises(ClientException):
            call('directoryservices.health.check')

        call('directoryservices.health.recover')

        assert check_ad_started() is True


def test_keytab_restore():

    with directoryservice('ACTIVEDIRECTORY', retrieve_user=False):
        reset_systemd_svcs('winbind')
        assert check_ad_started() is True

        kt_id = call('kerberos.keytab.query', [['name', '=', 'AD_MACHINE_ACCOUNT']], {'get': True})['id']

        # delete our keytab from datastore
        call('datastore.delete', 'directoryservice.kerberoskeytab', kt_id)

        call('directoryservices.health.recover')

        # verify that it was recreated during health check
        call('kerberos.keytab.query', [['name', '=', 'AD_MACHINE_ACCOUNT']], {'get': True})


def test_reset_directory_services():
    """ Verify that resetting the directory services config to NULL values doesn't break
    the schema parser. """
    call('directoryservices.reset')
    call('directoryservices.config')
