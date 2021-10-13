#!/usr/bin/env python3

import os
import json
import sys
import pytest
from pytest_dependency import depends
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import pool_name, ip, hostname, user, password
from functions import GET, POST, PUT, DELETE, SSH_TEST, cmd_test, wait_on_job

try:
    from config import AD_DOMAIN, ADPASSWORD, ADUSERNAME, ADNameServer
    # AD_USER is use for API call and CMD_AD_USER for command
    # r-string is use for raw string to stop pytest and flake8 complaining
    # about \
    AD_USER = fr"AD01\{ADUSERNAME.lower()}"
    CMD_AD_USER = fr"AD01\\{ADUSERNAME.lower()}"
except ImportError:
    Reason = 'ADNameServer AD_DOMAIN, ADPASSWORD, or/and ADUSERNAME are missing in config.py"'
    pytestmark = pytest.mark.skip(reason=Reason)
else:
    from auto_config import dev_test
    # comment pytestmark for development testing with --dev-test
    pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')

ad_data_type = {
    'id': int,
    'domainname': str,
    'bindname': str,
    'bindpw': str,
    'verbose_logging': bool,
    'allow_trusted_doms': bool,
    'use_default_domain': bool,
    'allow_dns_updates': bool,
    'disable_freenas_cache': bool,
    'site': type(None),
    'kerberos_realm': type(None),
    'kerberos_principal': str,
    'createcomputer': str,
    'timeout': int,
    'dns_timeout': int,
    'nss_info': type(None),
    'enable': bool,
    'netbiosname': str,
    'netbiosalias': list
}

ad_object_list = [
    "bindname",
    "domainname",
    "netbiosname",
    "enable"
]

dataset = f"{pool_name}/ad_share"
dataset_url = dataset.replace('/', '%2F')
SMB_NAME = "TestADShare"
SMB_PATH = f"/mnt/{dataset}"


@pytest.mark.dependency(name="ad_01")
def test_01_get_nameserver1(request):
    global nameserver1
    results = GET("/network/configuration/")
    assert results.status_code == 200, results.text
    nameserver1 = results.json()['nameserver1']


@pytest.mark.dependency(name="ad_02")
def test_02_set_nameserver_for_ad(request):
    depends(request, ["ad_01"], scope="session")
    global payload
    payload = {
        "nameserver1": ADNameServer,
    }
    global results
    results = PUT("/network/configuration/", payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


def test_03_get_activedirectory_data(request):
    depends(request, ["ad_01", "ad_02"], scope="session")
    global results
    results = GET('/activedirectory/')
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('data', list(ad_data_type.keys()))
def test_04_verify_activedirectory_data_type_of_the_object_value_of_(request, data):
    depends(request, ["ad_02"], scope="session")
    assert isinstance(results.json()[data], ad_data_type[data]), results.text


def test_05_get_activedirectory_state(request):
    depends(request, ["ad_01", "ad_02"], scope="session")
    results = GET('/activedirectory/get_state/')
    assert results.status_code == 200, results.text
    assert results.json() == 'DISABLED', results.text


def test_06_get_activedirectory_started_before_starting_activedirectory(request):
    depends(request, ["ad_01", "ad_02"], scope="session")
    results = GET('/activedirectory/started/')
    assert results.status_code == 200, results.text
    assert results.json() is False, results.text


@pytest.mark.dependency(name="ad_setup")
def test_07_enabling_activedirectory(request):
    depends(request, ["ad_01", "ad_02"], scope="session")
    global payload, results
    payload = {
        "bindpw": ADPASSWORD,
        "bindname": ADUSERNAME,
        "domainname": AD_DOMAIN,
        "netbiosname": hostname,
        "dns_timeout": 15,
        "verbose_logging": True,
        "enable": True
    }
    results = PUT("/activedirectory/", payload)
    assert results.status_code == 200, results.text
    job_status = wait_on_job(results.json()['job_id'], 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_08_verify_activedirectory_do_not_leak_password_in_middleware_log(request):
    depends(request, ["ad_setup", "ssh_password"], scope="session")
    cmd = f"""grep -R "{ADPASSWORD}" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_09_get_activedirectory_state(request):
    depends(request, ["ad_setup"], scope="session")
    global results
    results = GET('/activedirectory/get_state/')
    assert results.status_code == 200, results.text
    assert results.json() == 'HEALTHY', results.text


@pytest.mark.dependency(name="ad_dataset")
def test_10_creating_ad_dataset_for_smb(request):
    depends(request, ["pool_04", "ad_setup"], scope="session")
    payload = {
        "name": dataset,
        "share_type": "SMB"
    }
    results = POST("/pool/dataset/", payload)
    assert results.status_code == 200, results.text


@pytest.mark.dependency(name="ad_dataset_permission")
def test_11_changing_permissions_on_dataset(request):
    depends(request, ['ad_dataset'])
    obj_payload = {
        "username": AD_USER
    }
    global ldap_id
    results = POST("/user/get_user_obj/", obj_payload)
    assert results.status_code == 200, results.text
    payload = {
        'path': SMB_PATH,
        'uid': results.json()['pw_uid'],
    }
    results = POST('/filesystem/chown/', payload)
    assert results.status_code == 200, results.text
    job_status = wait_on_job(results.json(), 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_12_get_activedirectory_started(request):
    depends(request, ["ad_dataset_permission"], scope="session")
    results = GET('/activedirectory/started/')
    assert results.status_code == 200, results.text
    assert results.json() is True, results.text


def test_13_get_activedirectory_data(request):
    depends(request, ["ad_dataset_permission"], scope="session")
    global results
    results = GET('/activedirectory/')
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('data', ad_object_list)
def test_14_verify_activedirectory_data_of_(request, data):
    depends(request, ["ad_dataset_permission"], scope="session")
    if data == 'domainname':
        assert results.json()[data].lower() == payload[data], results.text
    else:
        assert results.json()[data] == payload[data], results.text


@pytest.mark.dependency(name="kerberos_verified")
def test_15_kerberos_keytab_verify(request):
    depends(request, ["ad_dataset_permission", "ssh_password"], scope="session")
    cmd = 'midclt call kerberos.keytab.kerberos_principal_choices'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    if results['result'] is True:
        kt = json.loads(results['output'].strip())
        assert len(kt) != 0, results['output']


def test_16_kerberos_restart_verify(request):
    """
    This tests our ability to re-kinit using our machine account.
    """
    depends(request, ["kerberos_verified", "ssh_password"], scope="session")
    cmd = 'rm /etc/krb5.keytab'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']

    cmd = 'midclt call kerberos.stop'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']

    cmd = 'midclt call kerberos.start'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']

    cmd = 'midclt call kerberos.keytab.kerberos_principal_choices'
    results = SSH_TEST(cmd, user, password, ip)
    kt = json.loads(results['output'].strip())
    assert results['result'] is True, results['output']
    assert len(kt) != 0, results['output']

    cmd = 'midclt call kerberos._klist_test'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['output'].strip() == 'True'


def test_17_setting_up_smb(request):
    depends(request, ["ad_dataset_permission"], scope="session")
    global payload, results
    payload = {
        "description": "Test TrueNAS Server",
    }
    results = PUT("/smb/", payload)
    assert results.status_code == 200, results.text
    assert results.json()["description"] == payload["description"], results.text


def test_18_verify_activedirectory_is_still_started_after_setting_smb(request):
    depends(request, ["ad_dataset_permission"], scope="session")
    results = GET('/activedirectory/started/')
    assert results.status_code == 200, results.text
    assert results.json() is True, results.text


def test_19_get_smb_data(request):
    depends(request, ["ad_dataset_permission"], scope="session")
    global results
    results = GET("/smb/")
    assert results.status_code == 200, results.text
    assert results.json()["description"] == payload["description"], results.text


def test_20_creating_a_smb_share_on_smb_path(request):
    depends(request, ["ad_dataset_permission"], scope="session")
    global payload, results, smb_id
    payload = {
        "comment": "My AD SMB Share",
        "path": SMB_PATH,
        "name": SMB_NAME,
        "streams": True
    }
    results = POST("/sharing/smb/", payload)
    assert results.status_code == 200, results.text
    smb_id = results.json()['id']


def test_21_verify_activedirectory_still_started_after_adding_a_share(request):
    depends(request, ["ad_dataset_permission"], scope="session")
    results = GET('/activedirectory/started/')
    assert results.status_code == 200, results.text
    assert results.json() is True, results.text


@pytest.mark.parametrize('data', ["comment", "path", "name"])
def test_22_verify_the_value_of_the_created_sharing_smb_object_(request, data):
    depends(request, ["ad_dataset_permission"], scope="session")
    assert results.json()[data] == payload[data], results.text


def test_23_get_sharing_smb_from_id(request):
    depends(request, ["ad_dataset_permission"], scope="session")
    global results
    results = GET(f"/sharing/smb/id/{smb_id}/")
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('data', ["comment", "path", "name"])
def test_24_verify_the_value_of_get_sharing_smb_object_(request, data):
    depends(request, ["ad_dataset_permission"], scope="session")
    assert results.json()[data] == payload[data], results.text


def test_25_enable_cifs_service(request):
    depends(request, ["ad_dataset_permission"], scope="session")
    results = PUT("/service/id/cifs/", {"enable": True})
    assert results.status_code == 200, results.text


def test_26_checking_to_see_if_clif_service_is_enabled(request):
    depends(request, ["ad_dataset_permission"], scope="session")
    results = GET("/service?service=cifs")
    assert results.json()[0]["enable"] is True, results.text


def test_27_starting_cifs_service(request):
    depends(request, ["ad_dataset_permission"], scope="session")
    payload = {"service": "cifs"}
    results = POST("/service/restart/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_28_checking_to_see_if_cifs_service_is_running(request):
    depends(request, ["ad_dataset_permission"], scope="session")
    results = GET("/service?service=cifs")
    assert results.json()[0]["state"] == "RUNNING", results.text


def test_29_verify_activedirectory_started_after_restarting_cifs(request):
    depends(request, ["ad_dataset_permission"], scope="session")
    results = GET('/activedirectory/started/')
    assert results.status_code == 200, results.text
    assert results.json() is True, results.text


def test_30_create_a_file_and_put_on_the_active_directory_share(request):
    depends(request, ["ad_dataset_permission"])
    cmd_test('touch testfile.txt')
    command = f'smbclient //{ip}/{SMB_NAME} -U {CMD_AD_USER}%{ADPASSWORD}' \
        ' -c "put testfile.txt testfile.txt"'
    results = cmd_test(command)
    cmd_test('rm testfile.txt')
    assert results['result'] is True, f'out: {results["output"]}, err: {results["stderr"]}'


def test_31_verify_testfile_is_on_the_active_directory_share(request):
    depends(request, ["ad_dataset_permission"])
    results = POST('/filesystem/stat/', f'{SMB_PATH}/testfile.txt')
    assert results.status_code == 200, results.text


def test_32_create_a_directory_on_the_active_directory_share(request):
    depends(request, ["ad_dataset_permission"])
    command = f'smbclient //{ip}/{SMB_NAME} -U {CMD_AD_USER}%{ADPASSWORD}' \
        ' -c "mkdir testdir"'
    results = cmd_test(command)
    assert results['result'] is True, f'out: {results["output"]}, err: {results["stderr"]}'


def test_33_verify_testdir_exist_on_the_active_directory_share(request):
    depends(request, ["ad_dataset_permission"])
    results = POST('/filesystem/stat/', f'{SMB_PATH}/testdir')
    assert results.status_code == 200, results.text


def test_34_copy_testfile_in_testdir_on_the_active_directory_share(request):
    depends(request, ["ad_dataset_permission"])
    command = f'smbclient //{ip}/{SMB_NAME} -U {CMD_AD_USER}%{ADPASSWORD}' \
        ' -c "scopy testfile.txt testdir/testfile2.txt"'
    results = cmd_test(command)
    assert results['result'] is True, f'out: {results["output"]}, err: {results["stderr"]}'


def test_35_verify_testfile2_exist_in_testdir_on_the_active_directory_share(request):
    depends(request, ["ad_dataset_permission"])
    results = POST('/filesystem/stat/', f'{SMB_PATH}/testdir/testfile2.txt')
    assert results.status_code == 200, results.text


def test_36_leave_activedirectory(request):
    depends(request, ["ad_dataset_permission"], scope="session")
    global payload, results
    payload = {
        "username": ADUSERNAME,
        "password": ADPASSWORD
    }
    results = POST("/activedirectory/leave/", payload)
    assert results.status_code == 200, results.text
    job_status = wait_on_job(results.json(), 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_37_verify_activedirectory_leave_do_not_leak_password_in_middleware_log(request):
    depends(request, ["ad_dataset_permission", "ssh_password"], scope="session")
    cmd = f"""grep -R "{ADPASSWORD}" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_38_get_activedirectory_state(request):
    depends(request, ["ad_dataset_permission"], scope="session")
    results = GET('/activedirectory/get_state/')
    assert results.status_code == 200, results.text
    assert results.json() == 'DISABLED', results.text


def test_39_get_activedirectory_started_after_leaving_AD(request):
    depends(request, ["ad_dataset_permission"], scope="session")
    results = GET('/activedirectory/started/')
    assert results.status_code == 200, results.text
    assert results.json() is False, results.text


def test_40_re_enable_activedirectory(request):
    depends(request, ["ad_dataset_permission"], scope="session")
    global payload, results
    payload = {
        "bindpw": ADPASSWORD,
        "bindname": ADUSERNAME,
        "domainname": AD_DOMAIN,
        "netbiosname": hostname,
        "enable": True
    }
    results = PUT("/activedirectory/", payload)
    assert results.status_code == 200, results.text
    job_status = wait_on_job(results.json()['job_id'], 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_41_verify_activedirectory_do_not_leak_password_in_middleware_log(request):
    depends(request, ["ad_dataset_permission", "ssh_password"], scope="session")
    cmd = f'grep -R "{ADPASSWORD}" /var/log/middlewared.log'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_42_get_activedirectory_state(request):
    depends(request, ["ad_dataset_permission"], scope="session")
    global results
    results = GET('/activedirectory/get_state/')
    assert results.status_code == 200, results.text
    assert results.json() == 'HEALTHY', results.text


def test_43_get_activedirectory_started(request):
    depends(request, ["ad_dataset_permission"], scope="session")
    results = GET('/activedirectory/started/')
    assert results.status_code == 200, results.text
    assert results.json() is True, results.text


def test_44_get_activedirectory_data(request):
    depends(request, ["ad_dataset_permission"], scope="session")
    global results
    results = GET('/activedirectory/')
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('data', ad_object_list)
def test_45_verify_activedirectory_data_of_(request, data):
    depends(request, ["ad_dataset_permission"], scope="session")
    if data == 'domainname':
        assert results.json()[data].lower() == payload[data], results.text
    else:
        assert results.json()[data] == payload[data], results.text


def test_46_verify_all_files_are_kept_on_the_active_directory_share(request):
    depends(request, ["ad_dataset_permission"])
    results = POST('/filesystem/stat/', f'{SMB_PATH}/testfile.txt')
    assert results.status_code == 200, results.text
    results = POST('/filesystem/stat/', f'{SMB_PATH}/testdir/testfile2.txt')
    assert results.status_code == 200, results.text


def test_47_delete_testfile_on_the_active_directory_share(request):
    depends(request, ["ad_dataset_permission"])
    command = fr'smbclient //{ip}/{SMB_NAME} -U {CMD_AD_USER}%{ADPASSWORD}' \
        ' -c "rm testfile.txt"'
    results = cmd_test(command)
    assert results['result'] is True, f'out: {results["output"]}, err: {results["stderr"]}'


def test_48_verify_testfile_is_deleted_on_the_active_directory_share(request):
    depends(request, ["ad_dataset_permission"])
    results = POST('/filesystem/stat/', f'{SMB_PATH}/testfile.txt')
    assert results.status_code == 422, results.text


def test_49_delele_testfile_on_the_active_directory_share(request):
    depends(request, ["ad_dataset_permission"])
    command = f'smbclient //{ip}/{SMB_NAME} -U {CMD_AD_USER}%{ADPASSWORD}' \
        ' -c "rm testdir/testfile2.txt"'
    results = cmd_test(command)
    assert results['result'] is True, f'out: {results["output"]}, err: {results["stderr"]}'


def test_50_verify_testfile2_is_deleted_on_the_active_directory_share(request):
    depends(request, ["ad_dataset_permission"])
    results = POST('/filesystem/stat/', f'{SMB_PATH}/testdir/testfile2.txt')
    assert results.status_code == 422, results.text


def test_51_delete_testdir_on_the_active_directory_share(request):
    depends(request, ["ad_dataset_permission"])
    command = f'smbclient //{ip}/{SMB_NAME} -U {CMD_AD_USER}%{ADPASSWORD}' \
        ' -c "rmdir testdir"'
    results = cmd_test(command)
    assert results['result'] is True, f'out: {results["output"]}, err: {results["stderr"]}'


def test_52_verify_testdir_is_deleted_on_the_active_directory_share(request):
    depends(request, ["ad_dataset_permission"])
    results = POST('/filesystem/stat/', f'{SMB_PATH}/testdir')
    assert results.status_code == 422, results.text


# put all code to disable and delete under here
def test_53_disable_activedirectory(request):
    depends(request, ["ad_dataset_permission"], scope="session")
    global payload, results
    payload = {
        "enable": False
    }
    results = PUT("/activedirectory/", payload)
    assert results.status_code == 200, results.text
    job_status = wait_on_job(results.json()['job_id'], 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_54_get_activedirectory_state(request):
    depends(request, ["ad_dataset_permission"], scope="session")
    results = GET('/activedirectory/get_state/')
    assert results.status_code == 200, results.text
    assert results.json() == 'DISABLED', results.text


def test_55_get_activedirectory_started_after_disabling_AD(request):
    depends(request, ["ad_dataset_permission"], scope="session")
    results = GET('/activedirectory/started/')
    assert results.status_code == 200, results.text
    assert results.json() is False, results.text


def test_56_re_enable_activedirectory(request):
    depends(request, ["ad_dataset_permission"], scope="session")
    global payload, results
    payload = {
        "enable": True
    }
    results = PUT("/activedirectory/", payload)
    assert results.status_code == 200, results.text
    job_status = wait_on_job(results.json()['job_id'], 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_57_get_activedirectory_state(request):
    depends(request, ["ad_dataset_permission"], scope="session")
    global results
    results = GET('/activedirectory/get_state/')
    assert results.status_code == 200, results.text
    assert results.json() == 'HEALTHY', results.text


def test_58_get_activedirectory_started(request):
    depends(request, ["ad_dataset_permission"], scope="session")
    results = GET('/activedirectory/started/')
    assert results.status_code == 200, results.text
    assert results.json() is True, results.text


def test_59_leave_activedirectory(request):
    depends(request, ["ad_dataset_permission"], scope="session")
    global payload, results
    payload = {
        "username": ADUSERNAME,
        "password": ADPASSWORD
    }
    results = POST("/activedirectory/leave/", payload)
    assert results.status_code == 200, results.text
    job_status = wait_on_job(results.json(), 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_60_verify_activedirectory_leave_do_not_leak_password_in_middleware_log(request):
    depends(request, ["ad_dataset_permission", "ssh_password"], scope="session")
    cmd = f"""grep -R "{ADPASSWORD}" /var/log/middlewared.log"""
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, str(results['output'])


def test_61_get_activedirectory_state(request):
    depends(request, ["ad_dataset_permission"], scope="session")
    results = GET('/activedirectory/get_state/')
    assert results.status_code == 200, results.text
    assert results.json() == 'DISABLED', results.text


def test_62_get_activedirectory_started_after_living(request):
    depends(request, ["ad_dataset_permission"], scope="session")
    results = GET('/activedirectory/started/')
    assert results.status_code == 200, results.text
    assert results.json() is False, results.text


def test_63_disable_cifs_service_at_boot(request):
    depends(request, ["ad_dataset_permission"], scope="session")
    results = PUT("/service/id/cifs/", {"enable": False})
    assert results.status_code == 200, results.text


def test_64_checking_to_see_if_clif_service_is_enabled_at_boot(request):
    depends(request, ["ad_dataset_permission"], scope="session")
    results = GET("/service?service=cifs")
    assert results.json()[0]["enable"] is False, results.text


def test_65_stoping_clif_service(request):
    depends(request, ["ad_dataset_permission"], scope="session")
    payload = {"service": "cifs"}
    results = POST("/service/stop/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_66_checking_if_cifs_is_stop(request):
    depends(request, ["ad_dataset_permission"], scope="session")
    results = GET("/service?service=cifs")
    assert results.json()[0]['state'] == "STOPPED", results.text


def test_67_destroying_ad_dataset_for_smb(request):
    depends(request, ["ad_dataset"], scope="session")
    results = DELETE(f"/pool/dataset/id/{dataset_url}/")
    assert results.status_code == 200, results.text


def test_68_configure_setting_domain_hostname_and_dns(request):
    depends(request, ["ad_01", "ad_02"], scope="session")
    global payload
    payload = {
        "nameserver1": nameserver1,
    }
    global results
    results = PUT("/network/configuration/", payload)
    assert results.status_code == 200, results.text
