#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os
import json
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET, DELETE, SSH_TEST, cmd_test, wait_on_job
from auto_config import ip, pool_name, password, user
from pytest_dependency import depends

dataset = f"{pool_name}/smb-cifs"
dataset_url = dataset.replace('/', '%2F')
SMB_NAME = "TestCifsSMB"
SMB_PATH = "/mnt/" + dataset

smb_acl = [
    {
        "tag": 'USER',
        "id": 1001,
        "type": "ALLOW",
        "perms": {"BASIC": "FULL_CONTROL"},
        "flags": {"BASIC": "INHERIT"}
    },
    {
        "tag": "owner@",
        "id": None,
        "type": "ALLOW",
        "perms": {"BASIC": "FULL_CONTROL"},
        "flags": {"BASIC": "INHERIT"}
    },
    {
        "tag": "group@",
        "id": None,
        "type": "ALLOW",
        "perms": {"BASIC": "FULL_CONTROL"},
        "flags": {"BASIC": "INHERIT"}
    }
]

guest_path_verification = {
    "user": "shareuser",
    "group": 'wheel',
    "acl": True
}


root_path_verification = {
    "user": "root",
    "group": 'wheel',
    "acl": False
}


# Create tests
def test_001_setting_auxilary_parameters_for_mount_smbfs():
    toload = "lanman auth = yes\nntlm auth = yes \nraw NTLMv2 auth = yes"
    payload = {
        "smb_options": toload,
        "enable_smb1": True,
        "guest": "shareuser"
    }
    results = PUT("/smb/", payload)
    assert results.status_code == 200, results.text


def test_002_creating_smb_dataset():
    payload = {
        "name": dataset,
        "share_type": "SMB"
    }
    results = POST("/pool/dataset/", payload)
    assert results.status_code == 200, results.text


def test_003_changing_dataset_permissions_of_smb_dataset():
    global job_id
    payload = {
        "acl": smb_acl,
        "user": "shareuser",
        "group": "wheel",
    }
    results = POST(f"/pool/dataset/id/{dataset_url}/permission/", payload)
    assert results.status_code == 200, results.text
    job_id = results.json()


def test_004_verify_the_job_id_is_successfull():
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_005_get_filesystem_stat_from_smb_path_and_verify_acl_is_true():
    results = POST('/filesystem/stat/', SMB_PATH)
    assert results.status_code == 200, results.text
    assert results.json()['acl'] is True, results.text


def test_006_starting_cifs_service_at_boot():
    results = PUT("/service/id/cifs/", {"enable": True})
    assert results.status_code == 200, results.text


def test_007_checking_to_see_if_clif_service_is_enabled_at_boot():
    results = GET("/service?service=cifs")
    assert results.json()[0]["enable"] is True, results.text


def test_008_creating_a_smb_share_path():
    global payload, results, smb_id
    payload = {
        "comment": "My Test SMB Share",
        "path": SMB_PATH,
        "home": False,
        "name": SMB_NAME,
        "guestok": True,
    }
    results = POST("/sharing/smb/", payload)
    assert results.status_code == 200, results.text
    smb_id = results.json()['id']


def test_009_starting_cifs_service():
    payload = {"service": "cifs"}
    results = POST("/service/start/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_010_checking_to_see_if_nfs_service_is_running():
    results = GET("/service?service=cifs")
    assert results.json()[0]["state"] == "RUNNING", results.text


def test_011_verify_smbclient_127_0_0_1_connection():
    cmd = 'smbclient -NL //127.0.0.1'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert 'TestCifsSMB' in results['output'], results['output']
    assert 'My Test SMB Share' in results['output'], results['output']


def test_012_create_a_file_and_put_on_the_active_directory_share(request):
    cmd_test('touch testfile.txt')
    command = f'smbclient //{ip}/{SMB_NAME} -U guest%none' \
        ' -m NT1 -c "put testfile.txt testfile.txt"'
    print(command)
    results = cmd_test(command)
    cmd_test('rm testfile.txt')
    assert results['result'] is True, results['output']


def test_013_verify_testfile_is_on_the_active_directory_share():
    results = POST('/filesystem/stat/', f'{SMB_PATH}/testfile.txt')
    assert results.status_code == 200, results.text


def test_014_create_a_directory_on_the_active_directory_share(request):
    command = f'smbclient //{ip}/{SMB_NAME} -U guest%none' \
        ' -m NT1 -c "mkdir testdir"'
    print(command)
    results = cmd_test(command)
    assert results['result'] is True, results['output']


def test_015_verify_testdir_exist_on_the_active_directory_share():
    results = POST('/filesystem/stat/', f'{SMB_PATH}/testdir')
    assert results.status_code == 200, results.text


def test_016_copy_testfile_in_testdir_on_the_active_directory_share(request):
    command = f'smbclient //{ip}/{SMB_NAME} -U guest%none' \
        ' -m NT1 -c "scopy testfile.txt testdir/testfile2.txt"'
    print(command)
    results = cmd_test(command)
    assert results['result'] is True, results['output']


def test_017_verify_testfile2_exist_in_testdir_on_the_active_directory_share():
    results = POST('/filesystem/stat/', f'{SMB_PATH}/testdir/testfile2.txt')
    assert results.status_code == 200, results.text


def test_018_setting_enable_smb1_to_false():
    payload = {
        "enable_smb1": False
    }
    results = PUT("/smb/", payload)
    assert results.status_code == 200, results.text


def test_019_change_sharing_smd_home_to_true_and_set_guestok_to_false():
    payload = {
        'home': True,
        "guestok": False
    }
    results = PUT(f"/sharing/smb/id/{smb_id}", payload)
    assert results.status_code == 200, results.text


def test_020_verify_smb_getparm_path_homes():
    cmd = 'midclt call smb.getparm path homes'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert results['output'].strip() == f'{SMB_PATH}/%U'


def test_021_stoping_clif_service():
    payload = {"service": "cifs"}
    results = POST("/service/stop/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_022_checking_if_cifs_is_stop():
    results = GET("/service?service=cifs")
    assert results.json()[0]['state'] == "STOPPED", results.text


def test_023_update_smb():
    payload = {"syslog": False}
    results = PUT("/smb/", payload)
    assert results.status_code == 200, results.text


def test_024_update_cifs_share():
    results = PUT(f"/sharing/smb/id/{smb_id}/", {"home": False})
    assert results.status_code == 200, results.text


def test_025_starting_cifs_service():
    payload = {"service": "cifs"}
    results = POST("/service/start/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_026_checking_to_see_if_nfs_service_is_running():
    results = GET("/service?service=cifs")
    assert results.json()[0]["state"] == "RUNNING", results.text


def test_027_verify_all_files_are_kept_on_the_active_directory_share():
    results = POST('/filesystem/stat/', f'{SMB_PATH}/testfile.txt')
    assert results.status_code == 200, results.text
    results = POST('/filesystem/stat/', f'{SMB_PATH}/testdir/testfile2.txt')
    assert results.status_code == 200, results.text


def test_028_delete_testfile_on_the_active_directory_share(request):
    command = f'smbclient //{ip}/{SMB_NAME} -U shareuser%testing' \
        ' -c "rm testfile.txt"'
    results = cmd_test(command)
    assert results['result'] is True, results['output']


def test_029_verify_testfile_is_deleted_on_the_active_directory_share():
    results = POST('/filesystem/stat/', f'{SMB_PATH}/testfile.txt')
    assert results.status_code == 422, results.text


def test_030_delele_testfile_on_the_active_directory_share(request):
    command = f'smbclient //{ip}/{SMB_NAME} -U shareuser%testing' \
        ' -c "rm testdir/testfile2.txt"'
    results = cmd_test(command)
    assert results['result'] is True, results['output']


def test_031_verify_testfile2_is_deleted_on_the_active_directory_share():
    results = POST('/filesystem/stat/', f'{SMB_PATH}/testdir/testfile2.txt')
    assert results.status_code == 422, results.text


def test_032_delete_testdir_on_the_active_directory_share(request):
    command = f'smbclient //{ip}/{SMB_NAME} -U shareuser%testing' \
        ' -c "rmdir testdir"'
    results = cmd_test(command)
    assert results['result'] is True, results['output']


def test_033_verify_testdir_is_deleted_on_the_active_directory_share():
    results = POST('/filesystem/stat/', f'{SMB_PATH}/testdir')
    assert results.status_code == 422, results.text


def test_034_change_timemachine_to_true():
    global vuid
    payload = {
        'timemachine': True,
    }
    results = PUT(f"/sharing/smb/id/{smb_id}/", payload)
    assert results.status_code == 200, results.text
    vuid = results.json()['vuid']


def test_035_verify_that_timemachine_is_true():
    results = GET(f"/sharing/smb/id/{smb_id}/")
    assert results.status_code == 200, results.text
    assert results.json()['timemachine'] is True, results.text


@pytest.mark.parametrize('vfs_object', ["ixnas", "fruit", "streams_xattr"])
def test_036_verify_smb_getparm_vfs_objects_share(vfs_object):
    cmd = f'midclt call smb.getparm "vfs objects" {SMB_NAME}'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert vfs_object in results['output'], results['output']


def test_037_verify_smb_getparm_fruit_time_machine_is_yes():
    cmd = f'midclt call smb.getparm "fruit:time machine" {SMB_NAME}'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert results['output'].strip() == 'yes', results['output']


def test_038_change_recyclebin_to_true():
    global vuid
    payload = {
        "recyclebin": True,
    }
    results = PUT(f"/sharing/smb/id/{smb_id}", payload)
    assert results.status_code == 200, results.text
    vuid = results.json()['vuid']


def test_039_verify_that_recyclebin_is_true():
    results = GET(f"/sharing/smb/id/{smb_id}/")
    assert results.status_code == 200, results.text
    assert results.json()['recyclebin'] is True, results.text


@pytest.mark.parametrize('vfs_object', ["ixnas", "crossrename", "recycle"])
def test_040_verify_smb_getparm_vfs_objects_share(vfs_object):
    cmd = f'midclt call smb.getparm "vfs objects" {SMB_NAME}'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert vfs_object in results['output'], results['output']


def test_041_create_a_file_and_put_on_the_active_directory_share(request):
    cmd_test('touch testfile.txt')
    command = f'smbclient //{ip}/{SMB_NAME} -U shareuser%testing' \
        ' -c "put testfile.txt testfile.txt"'
    print(command)
    results = cmd_test(command)
    cmd_test('rm testfile.txt')
    assert results['result'] is True, results['output']


def test_042_verify_testfile_is_on_the_active_directory_share():
    results = POST('/filesystem/stat/', f'{SMB_PATH}/testfile.txt')
    assert results.status_code == 200, results.text


def test_043_delete_testfile_on_the_active_directory_share(request):
    command = f'smbclient //{ip}/{SMB_NAME} -U shareuser%testing' \
        ' -c "rm testfile.txt"'
    results = cmd_test(command)
    assert results['result'] is True, results['output']


def test_044_verify_testfile_is_deleted_on_the_active_directory_share():
    results = POST('/filesystem/stat/', f'{SMB_PATH}/testfile.txt')
    assert results.status_code == 422, results.text


def test_045_verify_testfile_is_on_recycle_bin_in_the_active_directory_share():
    results = POST('/filesystem/stat/', f'{SMB_PATH}/.recycle/shareuser/testfile.txt')
    assert results.status_code == 200, results.text


def test_046_get_smb_sharesec_id_and_set_smb_sharesec_share_acl():
    global share_id, payload
    share_id = GET(f"/smb/sharesec/?share_name={SMB_NAME}").json()[0]['id']
    payload = {
        'share_acl': [
            {
                'ae_who_sid': 'S-1-5-32-544',
                'ae_perm': 'FULL',
                'ae_type': 'ALLOWED'
            }
        ]
    }
    results = PUT(f"/smb/sharesec/id/{share_id}/", payload)
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('ae', ['ae_who_sid', 'ae_perm', 'ae_type'])
def test_047_verify_smb_sharesec_change_for(ae):
    results = GET(f"/smb/sharesec/id/{share_id}/")
    assert results.status_code == 200, results.text
    ae_result = results.json()['share_acl'][0][ae]
    assert ae_result == payload['share_acl'][0][ae], results.text


def test_048_verify_midclt_call_smb_getparm_access_based_share_enum_is_null():
    cmd = f'midclt call smb.getparm "access based share enum" {SMB_NAME}'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert results['output'].strip() == 'null', results['output']


def test_049_delete_cifs_share():
    results = DELETE(f"/sharing/smb/id/{smb_id}")
    assert results.status_code == 200, results.text


@pytest.mark.dependency(name="SID_CHANGED")
def test_050_netbios_name_change_check_sid():
    """
    This test changes the netbios name of the server and then
    verifies that this results in the server's domain SID changing.
    The new SID is stored in a global variable so that we can
    perform additional tests to verify that SIDs are rewritten
    properly in group_mapping.tdb. old_netbiosname is stored so
    that we can reset configuration to what it was prior to the test.

    Test failure here shows that we failed to write our new SID
    to the configuration database.
    """
    global new_sid
    global old_netbiosname

    results = GET("/smb/")
    assert results.status_code == 200, results.text
    old_netbiosname = results.json()["netbiosname"]
    old_sid = results.json()["cifs_SID"]

    payload = {
        "netbiosname": "nb_new",
    }
    results = PUT("/smb/", payload)
    assert results.status_code == 200, results.text
    new_sid_resp = results.json()["cifs_SID"]
    assert old_sid != new_sid_resp, results.text
    sleep(5)

    results = GET("/smb/")
    assert results.status_code == 200, results.text
    new_sid = results.json()["cifs_SID"]
    assert new_sid != old_sid, results.text


@pytest.mark.dependency(name="SID_TEST_GROUP")
def test_051_create_new_smb_group_for_sid_test(request):
    """
    Create testgroup and verify that groupmap entry generated
    with new SID.
    """
    depends(request, ["SID_CHANGED"])
    global group_id
    payload = {
        "name": "testsidgroup",
        "smb": True,
    }
    results = POST("/group/", payload)
    assert results.status_code == 200, results.text
    group_id = results.json()
    sleep(5)

    cmd = "midclt call smb.groupmap_list"
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    groupmaps = json.loads(results['output'].strip())
    assert groupmaps.get("testsidgroup") is not None, groupmaps.keys()
    domain_sid = groupmaps["testsidgroup"]["SID"].rsplit("-", 1)[0]
    assert domain_sid == new_sid, groupmaps["testsidgroup"]


def test_052_change_netbios_name_and_check_groupmap(request):
    """
    Verify that changes to netbios name result in groupmap sid
    changes.
    """
    depends(request, ["SID_CHANGED"])
    payload = {
        "netbiosname": old_netbiosname,
    }
    results = PUT("/smb/", payload)
    assert results.status_code == 200, results.text
    sleep(5)

    cmd = "midclt call smb.groupmap_list"
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    groupmaps = json.loads(results['output'].strip())
    assert groupmaps.get("testsidgroup") is not None, groupmaps.keys()
    domain_sid = groupmaps["testsidgroup"]["SID"].rsplit("-", 1)[0]
    assert domain_sid != new_sid, groupmaps["testsidgroup"]


def test_053_delete_smb_group(request):
    depends(request, ["SID_TEST_GROUP"])
    results = DELETE(f"/group/id/{group_id}/")
    assert results.status_code == 200, results.text


# Now stop the service
def test_054_disable_cifs_service_at_boot():
    results = PUT("/service/id/cifs/", {"enable": False})
    assert results.status_code == 200, results.text


def test_055_checking_to_see_if_clif_service_is_enabled_at_boot():
    results = GET("/service?service=cifs")
    assert results.json()[0]["enable"] is False, results.text


def test_056_stoping_clif_service():
    payload = {"service": "cifs"}
    results = POST("/service/stop/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_057_checking_if_cifs_is_stop():
    results = GET("/service?service=cifs")
    assert results.json()[0]['state'] == "STOPPED", results.text


# Check destroying a SMB dataset
def test_058_destroying_smb_dataset():
    results = DELETE(f"/pool/dataset/id/{dataset_url}/")
    assert results.status_code == 200, results.text
