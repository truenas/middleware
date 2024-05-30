from contextlib import contextmanager
import os
import sys

import pytest

from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call

apifolder = os.getcwd()
sys.path.append(apifolder)

from middlewared.test.integration.assets.directory_service import active_directory, ldap
from auto_config import hostname, password, pool_name, user, ha
from functions import GET, POST, PUT, SSH_TEST, make_ws_request, wait_on_job
from protocols import nfs_share, SSH_NFS
from pytest_dependency import depends

try:
    from config import AD_DOMAIN, ADPASSWORD, ADUSERNAME, ADNameServer, AD_COMPUTER_OU
except ImportError:
    Reason = 'ADNameServer AD_DOMAIN, ADPASSWORD, or/and ADUSERNAME are missing in config.py"'
    pytestmark = pytest.mark.skip(reason=Reason)

pytestmark = pytest.mark.skip("LDAP KRB5 NFS tests disabled pending CI framework changes")


test_perms = {
    "READ_DATA": True,
    "WRITE_DATA": True,
    "EXECUTE": True,
    "APPEND_DATA": True,
    "DELETE_CHILD": False,
    "DELETE": True,
    "READ_ATTRIBUTES": True,
    "WRITE_ATTRIBUTES": True,
    "READ_NAMED_ATTRS": True,
    "WRITE_NAMED_ATTRS": True,
    "READ_ACL": True,
    "WRITE_ACL": True,
    "WRITE_OWNER": True,
    "SYNCHRONIZE": False,
}

test_flags = {
    "FILE_INHERIT": True,
    "DIRECTORY_INHERIT": True,
    "INHERIT_ONLY": False,
    "NO_PROPAGATE_INHERIT": False,
    "INHERITED": False
}


@pytest.fixture(scope="module")
def kerberos_config(request):
    # DNS in automation domain is often broken.
    # Setting rdns helps to pass this
    results = PUT("/kerberos/", {"libdefaults_aux": "rdns = false"})
    assert results.status_code == 200, results.text

    results = PUT("/nfs/", {"v4_krb": True})
    assert results.status_code == 200, results.text
    try:
        yield (request, results.json())
    finally:
        results = POST('/service/stop/', {'service': 'nfs'})
        assert results.status_code == 200, results.text

        results = PUT("/nfs/", {"v4_krb": False})
        assert results.status_code == 200, results.text

        results = PUT("/kerberos/", {"libdefaults_aux": ""})
        assert results.status_code == 200, results.text


@pytest.fixture(scope="module")
def do_ad_connection(request):
    with active_directory(
        AD_DOMAIN,
        ADUSERNAME,
        ADPASSWORD,
        netbiosname=hostname,
        createcomputer=AD_COMPUTER_OU,
    ) as ad:
        yield (request, ad)


@contextmanager
def stop_activedirectory(request):
    results = PUT("/activedirectory/", {"enable": False})
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    try:
        yield results.json()
    finally:
        results = PUT("/activedirectory/", {"enable": True})
        assert results.status_code == 200, results.text
        job_id = results.json()
        job_status = wait_on_job(job_id, 180)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])


@pytest.fixture(scope="module")
def do_ldap_connection(request):

    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'kerberos.keytab.kerberos_principal_choices',
        'params': [],
    })
    error = res.get('error')
    assert error is None, str(error)

    kerberos_principal = res['result'][0]

    results = GET("/kerberos/realm/")
    assert results.status_code == 200, results.text

    realm_id = results.json()[0]['id']

    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'kerberos.check_ticket',
        'params': [],
    })
    error = res.get('error')
    assert error is None, str(error)
    assert res['result'] is True

    results = POST("/activedirectory/domain_info/", AD_DOMAIN)
    assert results.status_code == 200, results.text
    domain_info = results.json()

    with stop_activedirectory(request) as ad:
        res = make_ws_request(ip, {
            'msg': 'method',
            'method': 'kerberos.get_cred',
            'params': [{
                'dstype': 'DS_TYPE_LDAP',
                'conf': {
                    'kerberos_realm': realm_id,
                    'kerberos_principal': kerberos_principal,
                }
            }],
        })
        error = res.get('error')
        assert error is None, str(error)
        cred = res['result']

        res = make_ws_request(ip, {
            'msg': 'method',
            'method': 'kerberos.do_kinit',
            'params': [{
                'krb5_cred': cred,
                'kinit-options': {
                    'kdc_override': {
                        'domain': AD_DOMAIN.upper(),
                        'kdc': domain_info['KDC server']
                    },
                }
            }],
        })
        error = res.get('error')
        assert error is None, str(error)

        with ldap(
            domain_info['Bind Path'],
            '', '', f'{domain_info["LDAP server name"].upper()}.',
            has_samba_schema=False,
            ssl="OFF",
            kerberos_realm=realm_id,
            kerberos_principal=kerberos_principal,
            validate_certificates=False,
            enable=True
        ) as ldap_conn:
            yield (request, ldap_conn)


@pytest.fixture(scope="module")
def setup_nfs_share(request):
    results = POST("/user/get_user_obj/", {'username': f'{ADUSERNAME}@{AD_DOMAIN}'})
    assert results.status_code == 200, results.text
    target_uid = results.json()['pw_uid']

    target_acl = [
        {'tag': 'owner@', 'id': -1, 'perms': test_perms, 'flags': test_flags, 'type': 'ALLOW'},
        {'tag': 'group@', 'id': -1, 'perms': test_perms, 'flags': test_flags, 'type': 'ALLOW'},
        {'tag': 'everyone@', 'id': -1, 'perms': test_perms, 'flags': test_flags, 'type': 'ALLOW'},
        {'tag': 'USER', 'id': target_uid, 'perms': test_perms, 'flags': test_flags, 'type': 'ALLOW'},
    ]
    with dataset(
        'NFSKRB5',
        {'acltype': 'NFSV4'},
        acl=target_acl
    ) as ds:
        with nfs_share(f'/mnt/{ds}', options={
            'comment': 'KRB Functional Test Share',
            'security': ['KRB5', 'KRB5I', 'KRB5P'],
        }) as share:
            yield (request, {'share': share, 'uid': target_uid})


@pytest.mark.dependency(name="AD_CONFIGURED")
def test_02_enabling_activedirectory(do_ad_connection):
    results = GET('/activedirectory/started/')
    assert results.status_code == 200, results.text
    assert results.json() is True, results.text

    results = GET('/activedirectory/get_state/')
    assert results.status_code == 200, results.text
    assert results.json() == 'HEALTHY', results.text


def test_03_kerberos_nfs4_spn_add(kerberos_config):
    depends(kerberos_config[0], ["AD_CONFIGURED"], scope="session")
    assert kerberos_config[1]['v4_krb_enabled']

    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'kerberos.keytab.has_nfs_principal',
        'params': [],
    })
    error = res.get('error')
    assert error is None, str(error)
    assert res['result'] is False

    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'nfs.add_principal',
        'params': [{
            'username': ADUSERNAME,
            'password': ADPASSWORD
        }],
    })
    error = res.get('error')
    assert error is None, str(error)
    assert res['result'] is True

    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'kerberos.keytab.has_nfs_principal',
        'params': [],
    })
    error = res.get('error')
    assert error is None, str(error)
    assert res['result'] is True

    results = POST('/service/reload/', {'service': 'idmap'})
    assert results.status_code == 200, results.text

    results = POST('/service/restart/', {'service': 'ssh'})
    assert results.status_code == 200, results.text


@pytest.mark.dependency(name="AD_LDAP_USER_CCACHE")
def test_05_kinit_as_ad_user(setup_nfs_share):
    """
    Set up an NFS share and ensure that permissions are
    set correctly to allow writes via out test user.

    This test does kinit as our test user so that we have
    kerberos ticket that we will use to verify NFS4 + KRB5
    work correctly.
    """
    depends(setup_nfs_share[0], ["AD_CONFIGURED"], scope="session")

    kinit_opts = {'ccache': 'USER', 'ccache_uid': setup_nfs_share[1]['uid']}

    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'kerberos.get_cred',
        'params': [{
            'dstype': 'DS_TYPE_ACTIVEDIRECTORY',
            'conf': {
                'domainname': AD_DOMAIN,
                'bindname': ADUSERNAME,
                'bindpw': ADPASSWORD,
            }
        }],
    })
    error = res.get('error')
    assert error is None, str(error)
    cred = res['result']

    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'kerberos.do_kinit',
        'params': [{
            'krb5_cred': cred,
            'kinit-options': kinit_opts
        }],
    })

    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'kerberos.check_ticket',
        'params': [kinit_opts],
    })
    error = res.get('error')
    assert error is None, str(error)
    assert res['result'] is True

    results = POST('/service/restart/', {'service': 'nfs'})
    assert results.status_code == 200, results.text


if not ha:
    """
    we skip this test for a myriad of profoundly complex reasons
    on our HA pipeline. If you cherish your sanity, don't try to
    understand, just accept and move on :)
    """
    def test_06_krb5nfs_ops_with_ad(request):
        my_fqdn = f'{hostname.strip()}.{AD_DOMAIN}'

        res = make_ws_request(ip, {
            'msg': 'method',
            'method': 'dnsclient.forward_lookup',
            'params': [{'names': [my_fqdn]}],
        })
        error = res.get('error')
        assert error is None, str(error)

        addresses = [rdata['address'] for rdata in res['result']]
        assert ip in addresses

        """
        The following creates a loopback mount using our kerberos
        keytab (AD computer account) and then performs ops via SSH
        using a limited AD account for which we generated a kerberos
        ticket above. Due to the odd nature of this setup, the loopback
        mount gets mapped as the guest account on the NFS server.
        This is fine for our purposes as we're validating that
        sec=krb5 works.
        """
        userobj = call('user.get_user_obj', {'username': f'{ADUSERNAME}@{AD_DOMAIN}'})
        groupobj = call('group.get_group_obj', {'gid': userobj['pw_gid']})
        call('ssh.update', {"password_login_groups": [groupobj['gr_name']]})
        with SSH_NFS(
            my_fqdn,
            f'/mnt/{pool_name}/NFSKRB5',
            vers=4,
            mount_user=user,
            mount_password=password,
            ip=ip,
            kerberos=True,
            user=ADUSERNAME,
            password=ADPASSWORD,
        ) as n:
            n.create('testfile')
            n.mkdir('testdir')
            contents = n.ls('.')

            assert 'testdir' in contents
            assert 'testfile' in contents

            file_acl = n.getacl('testfile')
            for idx, ace in enumerate(file_acl):
                assert ace['perms'] == test_perms, str(ace)

            dir_acl = n.getacl('testdir')
            for idx, ace in enumerate(dir_acl):
                assert ace['perms'] == test_perms, str(ace)
                assert ace['flags'] == test_flags, str(ace)

            n.unlink('testfile')
            n.rmdir('testdir')
            contents = n.ls('.')
            assert 'testdir' not in contents
            assert 'testfile' not in contents


@pytest.mark.dependency(name="SET_UP_AD_VIA_LDAP")
def test_07_setup_and_enabling_ldap(do_ldap_connection):
    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'kerberos.stop',
        'params': [],
    })
    error = res.get('error')
    assert error is None, str(error)

    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'kerberos.start',
        'params': [],
    })
    error = res.get('error')
    assert error is None, str(error)

    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'kerberos._klist_test',
        'params': [],
    })
    error = res.get('error')
    assert error is None, str(error)
    assert res['result'] is True

    # Verify that our NFS kerberos principal is
    # still present
    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'kerberos.keytab.has_nfs_principal',
        'params': [],
    })
    error = res.get('error')
    assert error is None, str(error)
    assert res['result'] is True


def test_08_verify_ldap_users(request):
    depends(request, ["SET_UP_AD_VIA_LDAP"], scope="session")

    results = GET('/user', payload={
        'query-filters': [['local', '=', False]],
        'query-options': {'extra': {"search_dscache": True}},
    })
    assert results.status_code == 200, results.text
    assert len(results.json()) > 0, results.text

    results = GET('/group', payload={
        'query-filters': [['local', '=', False]],
        'query-options': {'extra': {"search_dscache": True}},
    })
    assert results.status_code == 200, results.text
    assert len(results.json()) > 0, results.text
