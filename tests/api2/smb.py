#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os
import json
import re
from time import sleep
from datetime import datetime
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import (
    PUT,
    POST,
    GET,
    DELETE,
    SSH_TEST,
    cmd_test,
    send_file,
    wait_on_job
)
from auto_config import ip, pool_name, password, user
from pytest_dependency import depends

try:
    Reason = 'Windows host credential is missing in config.py'
    from config import WIN_HOST, WIN_USERNAME, WIN_PASSWORD
    windows_host_cred = pytest.mark.skipif(False, reason=Reason)
except ImportError:
    windows_host_cred = pytest.mark.skipif(True, reason=Reason)

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
    payload = {
        "acl": smb_acl,
        "user": "shareuser",
        "group": "wheel",
    }
    results = POST(f"/pool/dataset/id/{dataset_url}/permission/", payload)
    assert results.status_code == 200, results.text
    job_status = wait_on_job(results.json(), 180)
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


@windows_host_cred
def test_046_create_a_dir_and_a_file_in_windows():
    cmd1 = 'mkdir testdir'
    results = SSH_TEST(cmd1, WIN_USERNAME, WIN_PASSWORD, WIN_HOST)
    assert results['result'] is True, results['output']
    cmd2 = r'echo some-text  > testdir\testfile.txt'
    results = SSH_TEST(cmd2, WIN_USERNAME, WIN_PASSWORD, WIN_HOST)
    assert results['result'] is True, results['output']
    cmd3 = r'dir testdir\testfile.txt'
    results3 = SSH_TEST(cmd3, WIN_USERNAME, WIN_PASSWORD, WIN_HOST)
    assert results3['result'] is True, results3['output']
    regex = re.compile(r"^.*testfile.*", re.MULTILINE)
    data_list = regex.findall(results3['output'])[0].split()
    global created_time, created_date
    created_time = data_list[1]
    created_date = data_list[0]


@windows_host_cred
def test_047_mount_the_smb_share_robocopy_testdir_to_the_share_windows_mount():
    # sleep 61 second to make sure that
    sleep(61)
    script = '@echo on\n'
    script += fr'net use X: \\{ip}\{SMB_NAME} /user:shareuser testing'
    script += '\n'
    script += r'robocopy testdir X:\testdir /COPY:DAT'
    script += '\n'
    script += r'dir X:\testdir'
    script += '\nnet use X: /delete\n'
    cmd_file = open('runtest.cmd', 'w')
    cmd_file.writelines(script)
    cmd_file.close()
    results = send_file(
        'runtest.cmd',
        'runtest.cmd',
        WIN_USERNAME,
        WIN_PASSWORD,
        WIN_HOST
    )
    assert results['result'] is True, results['output']
    cmd_results = SSH_TEST('runtest.cmd', WIN_USERNAME, WIN_PASSWORD, WIN_HOST)
    assert cmd_results['result'] is True, cmd_results['output']
    os.remove("runtest.cmd")
    cmd = 'del runtest.cmd'
    results = SSH_TEST(cmd, WIN_USERNAME, WIN_PASSWORD, WIN_HOST)
    assert results['result'] is True, results['output']
    regex = re.compile(r"^(?=.*testfile)(?!.*New).*", re.MULTILINE)
    data_list = regex.findall(cmd_results['output'])[0].split()
    global mounted_time, mounted_date
    mounted_time = data_list[1]
    mounted_date = data_list[0]


@windows_host_cred
def test_048_verify_the_created_time_is_the_same_on_the_mounted_share():
    assert created_date == mounted_date
    assert created_time == mounted_time


@windows_host_cred
def test_049_verify_the_time_of_the_file_on_dataset_is_the_same_time_then_created_file():
    """
    The server running this test, then Windows VM and TrueNAS VM should run
    on same timezone. If not this test will failed.
    """
    results = POST('/filesystem/stat/', f'{SMB_PATH}/testdir/testfile.txt')
    assert results.status_code == 200, results.text
    atime = datetime.fromtimestamp(results.json()['atime'])
    mtime = datetime.fromtimestamp(results.json()['mtime'])
    assert created_date == atime.strftime('%m/%d/%Y')
    assert created_time == atime.strftime('%H:%M')
    assert created_date == mtime.strftime('%m/%d/%Y')
    assert created_time == mtime.strftime('%H:%M')


@windows_host_cred
def test_050_delete_the_test_dir_and_a_file_in_windows():
    cmd = 'rmdir /S /Q testdir'
    results = SSH_TEST(cmd, WIN_USERNAME, WIN_PASSWORD, WIN_HOST)
    assert results['result'] is True, results['output']


def test_051_get_smb_sharesec_id_and_set_smb_sharesec_share_acl():
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
def test_052_verify_smb_sharesec_change_for(ae):
    results = GET(f"/smb/sharesec/id/{share_id}/")
    assert results.status_code == 200, results.text
    ae_result = results.json()['share_acl'][0][ae]
    assert ae_result == payload['share_acl'][0][ae], results.text


def test_053_verify_midclt_call_smb_getparm_access_based_share_enum_is_null():
    cmd = f'midclt call smb.getparm "access based share enum" {SMB_NAME}'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert results['output'].strip() == 'null', results['output']


def test_054_delete_cifs_share():
    results = DELETE(f"/sharing/smb/id/{smb_id}")
    assert results.status_code == 200, results.text

def set_netbios_name(netbios_name):
    """
    Set NetbiosName in an HA-aware manner and return
    new config
    """
    cmd = "midclt call smb.get_smb_ha_mode"
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    ha_mode = results['output'].strip()

    assert ha_mode != 'LEGACY', 'LEGACY HA mode - possible error with sysdataset'

    if ha_mode == 'UNIFIED':
        payload = {"hostname_virtual": netbios_name}
        results = PUT("/network/configuration/", payload)
        assert results.status_code == 200, results.text

        results =  GET("/smb")
        assert results.status_code == 200, results.text
        return results.json()

    payload = {"netbiosname": netbios_name}
    results = PUT("/smb/", payload)
    assert results.status_code == 200, results.text
    return results.json()

@pytest.mark.dependency(name="SID_CHANGED")
def test_055_netbios_name_change_check_sid():
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
    old_netbiosname = results.json()["netbiosname_local"]
    old_sid = results.json()["cifs_SID"]

    new = set_netbios_name("nbnew")
    new_sid_resp = new["cifs_SID"]
    sleep(5)

    results = GET("/smb/")
    assert results.status_code == 200, results.text
    new_sid = results.json()["cifs_SID"]
    assert new_sid != old_sid, results.text


@pytest.mark.dependency(name="SID_TEST_GROUP")
def test_056_create_new_smb_group_for_sid_test(request):
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


def test_057_change_netbios_name_and_check_groupmap(request):
    """
    Verify that changes to netbios name result in groupmap sid
    changes.
    """
    depends(request, ["SID_CHANGED"])
    set_netbios_name(old_netbiosname)
    sleep(5)

    cmd = "midclt call smb.groupmap_list"
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    groupmaps = json.loads(results['output'].strip())
    assert groupmaps.get("testsidgroup") is not None, groupmaps.keys()
    domain_sid = groupmaps["testsidgroup"]["SID"].rsplit("-", 1)[0]
    assert domain_sid != new_sid, groupmaps["testsidgroup"]


def test_058_delete_smb_group(request):
    depends(request, ["SID_TEST_GROUP"])
    results = DELETE(f"/group/id/{group_id}/")
    assert results.status_code == 200, results.text


# Now stop the service
def test_059_disable_cifs_service_at_boot():
    results = PUT("/service/id/cifs/", {"enable": False})
    assert results.status_code == 200, results.text


def test_060_checking_to_see_if_clif_service_is_enabled_at_boot():
    results = GET("/service?service=cifs")
    assert results.json()[0]["enable"] is False, results.text


def test_061_stoping_clif_service():
    payload = {"service": "cifs"}
    results = POST("/service/stop/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_062_checking_if_cifs_is_stop():
    results = GET("/service?service=cifs")
    assert results.json()[0]['state'] == "STOPPED", results.text


# Check destroying a SMB dataset
def test_063_destroying_smb_dataset():
    results = DELETE(f"/pool/dataset/id/{dataset_url}/")
    assert results.status_code == 200, results.text
