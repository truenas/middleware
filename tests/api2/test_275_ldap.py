#!/usr/bin/env python3

import pytest
import sys
import os
import time
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import (
    GET,
    PUT,
    POST,
    DELETE,
    SSH_TEST,
    cmd_test,
    wait_on_job
)
from auto_config import pool_name, ip, user, password

from middlewared.test.integration.assets.directory_service import ldap
from middlewared.test.integration.assets.privilege import privilege
from middlewared.test.integration.assets.product import product_type
from middlewared.test.integration.utils import call, client

try:
    from config import (
        LDAPUSER,
        LDAPPASSWORD
    )
    pytestmark = pytest.mark.ds
except ImportError:
    Reason = 'LDAP* variable are not setup in config.py'
    pytestmark = pytest.mark.skipif(True, reason=Reason)

dataset = f"{pool_name}/ldap-test"
dataset_url = dataset.replace('/', '%2F')
smb_name = "TestLDAPShare"
smb_path = f"/mnt/{dataset}"
VOL_GROUP = "root"


@pytest.fixture(scope="module")
def do_ldap_connection(request):
    with ldap(has_samba_schema=True) as ldap_conn:
        with product_type():
            yield (request, ldap_conn)

def test_01_get_ldap():
    results = GET("/ldap/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


def test_02_verify_default_ldap_state_is_disabled():
    results = GET("/ldap/get_state/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), str), results.text
    assert results.json() == "DISABLED", results.text


def test_03_verify_ldap_enable_is_false():
    results = GET("/ldap/")
    assert results.json()["enable"] is False, results.text


def test_04_get_ldap_schema_choices():
    idmap_backend = {"RFC2307", "RFC2307BIS"}
    results = GET("/ldap/schema_choices/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    assert idmap_backend.issubset(set(results.json())), results.text


def test_05_get_ldap_ssl_choices():
    idmap_backend = {"OFF", "ON", "START_TLS"}
    results = GET("/ldap/ssl_choices/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    assert idmap_backend.issubset(set(results.json())), results.text


@pytest.mark.dependency(name="setup_ldap")
def test_06_setup_and_enabling_ldap(do_ldap_connection):
    results = GET("/ldap/get_state/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), str), results.text
    assert results.json() == "HEALTHY", results.text

    results = GET("/alert/list/")
    assert results.status_code == 200, results.text
    assert any([x for x in results.json() if x['klass'] == 'DeprecatedServiceConfiguration']), results.text


def test_08_verify_ldap_enable_is_true(request):
    depends(request, ["setup_ldap"], scope="session")
    results = GET("/ldap/")
    assert results.json()["enable"] is True, results.text
    assert results.json()["server_type"] == "OPENLDAP"


def test_09_account_privilege_authentication(request):
    depends(request, ["setup_ldap"], scope="session")

    call("system.general.update", {"ds_auth": True})
    try:
        gid = call("user.get_user_obj", {"username": LDAPUSER})["pw_gid"]
        with privilege({
            "name": "LDAP privilege",
            "local_groups": [],
            "ds_groups": [gid],
            "allowlist": [{"method": "CALL", "resource": "system.info"}],
            "web_shell": False,
        }):
            with client(auth=(LDAPUSER, LDAPPASSWORD)) as c:
                methods = c.call("core.get_methods")

            assert "system.info" in methods
            assert "pool.create" not in methods
    finally:
        call("system.general.update", {"ds_auth": False})


@pytest.mark.dependency(name="ldap_dataset")
def test_09_creating_ldap_dataset_for_smb(request):
    depends(request, ["setup_ldap"], scope="session")
    results = POST("/pool/dataset/", {"name": dataset, "share_type": "SMB"})
    assert results.status_code == 200, results.text


def test_10_verify_that_the_ldap_user_is_listed_with_pdbedit(request):
    depends(request, ["setup_ldap"], scope="session")
    results = SSH_TEST(f'pdbedit -L {LDAPUSER}', user, password, ip)
    assert results['result'] is True, str(results['output'])
    assert LDAPUSER in results['stdout'], str(results['output'])


@pytest.mark.dependency(name="LDAP_NSS_WORKING")
def test_11_verify_that_the_ldap_user_id_exist_on_the_nas(request):
    """
    get_user_obj is a wrapper around the pwd module.
    This check verifies that the user is _actually_ created.
    """
    depends(request, ["setup_ldap"])
    payload = {
        "username": LDAPUSER
    }
    global ldap_id
    results = POST("/user/get_user_obj/", payload)
    assert results.status_code == 200, results.text
    ldap_id = results.json()['pw_uid']


@pytest.mark.dependency(name="LDAP_DATASET_PERMISSION")
def test_12_changing_ldap_dataset_permission(request):
    """
    Make LDAP user owner of dataset. This is simplest way to
    ensure has permissions.
    """
    depends(request, ["setup_ldap", "ldap_dataset", "LDAP_NSS_WORKING"], scope="session")
    payload = {
        'path': smb_path,
        'uid': ldap_id,
    }
    results = POST('/filesystem/chown/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_13_setting_up_for_testing(request):
    depends(request, ["setup_ldap", "ldap_dataset", "LDAP_DATASET_PERMISSION"], scope="session")
    global payload, results
    payload = {
        "description": "Test FreeNAS Server",
    }
    results = PUT("/smb/", payload)
    assert results.status_code == 200, results.text


@pytest.mark.dependency(name="smb_share_ldap")
def test_14_creating_a_smb_share_to_test_ldap(request):
    depends(request, ["setup_ldap", "ldap_dataset", "LDAP_DATASET_PERMISSION"], scope="session")
    global smb_id
    payload = {
        "comment": "My Test SMB Share",
        "path": smb_path,
        "name": smb_name,
        "guestok": False,
        "streams": True
    }
    results = POST("/sharing/smb/", payload)
    assert results.status_code == 200, results.text
    smb_id = results.json()['id']


def test_15_enable_cifs_service(request):
    depends(request, ["setup_ldap", "ldap_dataset", "smb_share_ldap"], scope="session")
    results = PUT("/service/id/cifs/", {"enable": True})
    assert results.status_code == 200, results.text


def test_16_verify_if_clif_service_is_enabled(request):
    depends(request, ["setup_ldap", "ldap_dataset", "smb_share_ldap"], scope="session")
    results = GET("/service?service=cifs")
    assert results.json()[0]["enable"] is True, results.text


def test_17_starting_cifs_service(request):
    depends(request, ["setup_ldap", "ldap_dataset", "smb_share_ldap"], scope="session")
    payload = {"service": "cifs"}
    results = POST("/service/restart/", payload)
    assert results.status_code == 200, results.text
    time.sleep(5)


def test_18_verify_if_cifs_service_is_running(request):
    depends(request, ["setup_ldap", "ldap_dataset", "smb_share_ldap"], scope="session")
    results = GET("/service?service=cifs")
    assert results.json()[0]["state"] == "RUNNING", results.text


def test_19_verify_smbclient_connect_to_the_smb_share_with_ldap_with_ssl_on(request):
    depends(request, ["setup_ldap", "ldap_dataset", "smb_share_ldap"], scope="session")
    cmd = f'smbclient //{ip}/{smb_name} -U {LDAPUSER}%"{LDAPPASSWORD}" -c ls'
    results = cmd_test(cmd)
    assert results['result'] is True, results['output']


def test_20_create_a_testfile_and_send_it_to_the_smb_share_with_ldap(request):
    depends(request, ["setup_ldap", "ldap_dataset", "smb_share_ldap"], scope="session")
    cmd_test('touch testfile.txt')
    cmd = f'smbclient //{ip}/{smb_name} -U {LDAPUSER}%"{LDAPPASSWORD}"' \
        ' -c "put testfile.txt testfile.txt"'
    results = cmd_test(cmd)
    assert results['result'] is True, results['output']


def test_21_verify_testfile_exit_with_in_the_smb_share_with_filesystem_stat(request):
    depends(request, ["setup_ldap", "ldap_dataset", "smb_share_ldap"], scope="session")
    results = POST('/filesystem/stat/', f'{smb_path}/testfile.txt')
    assert results.status_code == 200, results.text


def test_22_set_has_samba_schema_to_false(request):
    depends(request, ["setup_ldap", "ldap_dataset", "smb_share_ldap"], scope="session")
    payload = {
        "has_samba_schema": False
    }
    results = PUT("/ldap/", payload)
    assert results.status_code == 200, results.text

    job_id = results.json()
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    results = GET("/alert/list/")
    assert results.status_code == 200, results.text
    assert not any([x for x in results.json() if x['klass'] == 'DeprecatedService']), results.text


def test_23_restarting_cifs_service_after_changing_has_samba_schema(request):
    depends(request, ["setup_ldap", "ldap_dataset", "smb_share_ldap"], scope="session")
    payload = {"service": "cifs"}
    results = POST("/service/restart/", payload)
    assert results.status_code == 200, results.text
    time.sleep(5)


def test_24_verify_that_the_ldap_user_is_not_listed_with_pdbedit(request):
    depends(request, ["setup_ldap", "ldap_dataset", "smb_share_ldap"], scope="session")
    results = SSH_TEST(f'pdbedit -L {LDAPUSER}', user, password, ip)
    assert results['result'] is False, results['output']


def test_25_verify_with_smbclient_that_ldap_user_cant_access_with_samba_schema_false(request):
    depends(request, ["setup_ldap", "ldap_dataset", "smb_share_ldap"], scope="session")
    cmd = f'smbclient //{ip}/{smb_name} -U {LDAPUSER}%"{LDAPPASSWORD}" -c ls'
    results = cmd_test(cmd)
    assert results['result'] is False, results['output']


def test_26_set_has_samba_schema_true_and_ssl_START_TLS(request):
    depends(request, ["setup_ldap", "ldap_dataset", "smb_share_ldap"], scope="session")
    payload = {
        "has_samba_schema": True,
        "ssl": "START_TLS",
    }
    results = PUT("/ldap/", payload)
    assert results.status_code == 200, results.text

    job_id = results.json()
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_27_starting_cifs_service_after_changing_ssl_to_START_TLS(request):
    depends(request, ["setup_ldap", "ldap_dataset", "smb_share_ldap"], scope="session")
    payload = {"service": "cifs"}
    results = POST("/service/restart/", payload)
    assert results.status_code == 200, results.text
    time.sleep(5)


def test_28_verify_if_cifs_service_is_running(request):
    depends(request, ["setup_ldap", "ldap_dataset", "smb_share_ldap"], scope="session")
    results = GET("/service?service=cifs")
    assert results.json()[0]["state"] == "RUNNING", results.text


def test_29_verify_that_the_ldap_user_is_listed_with_pdbedit(request):
    depends(request, ["setup_ldap", "ldap_dataset", "smb_share_ldap"], scope="session")
    results = SSH_TEST(f'pdbedit -L {LDAPUSER}', user, password, ip)
    assert results['result'] is True, results['output']


def test_30_verify_smbclient_connect_to_the_smb_share_with_ldap_with_ssl_START_TLS(request):
    depends(request, ["setup_ldap", "ldap_dataset", "smb_share_ldap"], scope="session")
    cmd = f'smbclient //{ip}/{smb_name} -U {LDAPUSER}%"{LDAPPASSWORD}" -c ls'
    results = cmd_test(cmd)
    assert results['result'] is True, results['output']


def test_31_remove_the_testfile_from_smb_share_with_ldap_with_ssl_START_TLS(request):
    depends(request, ["setup_ldap", "ldap_dataset", "smb_share_ldap"], scope="session")
    cmd = f'smbclient //{ip}/{smb_name} -U {LDAPUSER}%"{LDAPPASSWORD}"' \
        ' -c "rm testfile.txt"'
    results = cmd_test(cmd)
    assert results['result'] is True, results['output']
    cmd_test('rm testfile.txt')


def test_32_verify_testfile_is_removed_from_the_smb_share_with_filesystem_stat(request):
    depends(request, ["setup_ldap", "ldap_dataset", "smb_share_ldap"], scope="session")
    results = POST('/filesystem/stat/', f'{smb_path}/testfile.txt')
    assert results.status_code == 422, results.text


def test_33_set_has_samba_schema_to_false(request):
    depends(request, ["setup_ldap", "ldap_dataset", "smb_share_ldap"], scope="session")
    payload = {
        "has_samba_schema": False
    }
    results = PUT("/ldap/", payload)
    assert results.status_code == 200, results.text

    job_id = results.json()
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_34_restarting_cifs_service_after_changing_has_samba_schema(request):
    depends(request, ["setup_ldap", "ldap_dataset", "smb_share_ldap"], scope="session")
    payload = {"service": "cifs"}
    results = POST("/service/restart/", payload)
    assert results.status_code == 200, results.text


def test_35_verify_that_the_ldap_user_is_not_listed_with_pdbedit(request):
    depends(request, ["setup_ldap", "ldap_dataset", "smb_share_ldap"], scope="session")
    results = SSH_TEST(f'pdbedit -L {LDAPUSER}', user, password, ip)
    assert results['result'] is False, results['output']


def test_36_verify_with_smbclient_that_ldap_user_cant_access_with_samba_schema_false(request):
    depends(request, ["setup_ldap", "ldap_dataset", "smb_share_ldap"], scope="session")
    cmd = f'smbclient //{ip}/{smb_name} -U {LDAPUSER}%"{LDAPPASSWORD}" -c ls'
    results = cmd_test(cmd)
    assert results['result'] is False, results['output']


def test_37_stopping_cifs_service(request):
    depends(request, ["setup_ldap", "ldap_dataset", "smb_share_ldap"], scope="session")
    payload = {"service": "cifs"}
    results = POST("/service/stop/", payload)
    assert results.status_code == 200, results.text


def test_38_verify_if_cifs_service_stopped(request):
    depends(request, ["setup_ldap", "ldap_dataset", "smb_share_ldap"], scope="session")
    results = GET("/service?service=cifs")
    assert results.json()[0]["state"] == "STOPPED", results.text


def test_39_delete_the_smb_share_for_ldap_testing(request):
    depends(request, ["setup_ldap", "ldap_dataset", "smb_share_ldap"], scope="session")
    results = DELETE(f"/sharing/smb/id/{smb_id}")
    assert results.status_code == 200, results.text


def test_43_destroying_ldap_dataset_for_smb(request):
    depends(request, ["setup_ldap", "ldap_dataset"], scope="session")
    results = DELETE(f"/pool/dataset/id/{dataset_url}/")
    assert results.status_code == 200, results.text
