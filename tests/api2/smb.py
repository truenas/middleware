#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET, DELETE, SSH_TEST
from auto_config import ip, pool_name, password, user
from config import *


MOUNTPOINT = "/tmp/smb-cifs"
dataset = f"{pool_name}/smb-cifs"
dataset_url = dataset.replace('/', '%2F')
SMB_NAME = "TestCifsSMB"
SMB_PATH = "/mnt/" + dataset
VOL_GROUP = "wheel"
BSDReason = 'BSD host configuration is missing in ixautomation.conf'
OSXReason = 'OSX host configuration is missing in ixautomation.conf'

bsd_host_cfg = pytest.mark.skipif(all(["BSD_HOST" in locals(),
                                       "BSD_USERNAME" in locals(),
                                       "BSD_PASSWORD" in locals()
                                       ]) is False, reason=BSDReason)

osx_host_cfg = pytest.mark.skipif(all(["OSX_HOST" in locals(),
                                       "OSX_USERNAME" in locals(),
                                       "OSX_PASSWORD" in locals()
                                       ]) is False, reason=OSXReason)


# Create tests
def test_01_setting_auxilary_parameters_for_mount_smbfs():
    toload = "lanman auth = yes\nntlm auth = yes \nraw NTLMv2 auth = yes"
    payload = {
        "smb_options": toload,
        "enable_smb1": True,
        "guest": "shareuser"
    }
    results = PUT("/smb/", payload)
    assert results.status_code == 200, results.text


def test_02_creating_smb_dataset():
    payload = {
        "name": dataset,
        "share_type": "SMB"
    }
    results = POST("/pool/dataset/", payload)
    assert results.status_code == 200, results.text


def test_03_changing_dataset_permissions_of_smb_dataset():
    payload = {
        "acl": [],
        "mode": "777",
        "user": "shareuser",
        "group": "wheel",
        "options": {
        "stripacl": True
        }
    }
    results = POST(f"/pool/dataset/id/{dataset_url}/permission/", payload)
    assert results.status_code == 200, results.text


def test_04_starting_cifs_service_at_boot():
    results = PUT("/service/id/cifs/", {"enable": True})
    assert results.status_code == 200, results.text


def test_05_checking_to_see_if_clif_service_is_enabled_at_boot():
    results = GET("/service?service=cifs")
    assert results.json()[0]["enable"] is True, results.text


def test_06_creating_a_smb_share_path():
    global payload, results, smb_id
    payload = {
        "comment": "My Test SMB Share",
        "path": SMB_PATH,
        "home": False,
        "name": SMB_NAME,
        "guestok": True,
        "vfsobjects": ["streams_xattr"]
    }
    results = POST("/sharing/smb/", payload)
    assert results.status_code == 200, results.text
    smb_id = results.json()['id']


def test_07_verify_if_smb_getparm_path_homes_is_null():
    cmd = 'midclt call smb.getparm path homes'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert results['output'].strip() == 'null'


def test_08_starting_cifs_service():
    payload = {"service": "cifs", "service-control": {"onetime": True}}
    results = POST("/service/start/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_09_checking_to_see_if_nfs_service_is_running():
    results = GET("/service?service=cifs")
    assert results.json()[0]["state"] == "RUNNING", results.text


@bsd_host_cfg
def test_10_creating_smb_mountpoint_on_bsd():
    cmd = f'mkdir -p "{MOUNTPOINT}" && sync'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_11_mounting_smb_on_bsd():
    cmd = f'mount_smbfs -N -I {ip} ' \
        f'"//guest@testnas/{SMB_NAME}" "{MOUNTPOINT}"'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_12_creating_testfile_on_bsd():
    cmd = f"touch {MOUNTPOINT}/testfile.txt"
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_13_verify_testfile_exist_on_freenas():
    cmd = f'test -f "{SMB_PATH}/testfile.txt"'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_14_moving_smb_file_on_bsd():
    cmd = f'mv {MOUNTPOINT}/testfile.txt {MOUNTPOINT}/testfile2.txt'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_15_verify_testfile_does_not_exist_on_freenas():
    cmd = f'test -f "{SMB_PATH}/testfile.txt"'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, results['output']


@bsd_host_cfg
def test_16_verify_testfile2_exist_on_freenas():
    cmd = f'test -f "{SMB_PATH}/testfile2.txt"'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_17_copying_smb_file_on_bsd():
    cmd = f'cp {MOUNTPOINT}/testfile2.txt {MOUNTPOINT}/testfile.txt'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_18_verify_testfile_exist_on_freenas():
    cmd = f'test -f "{SMB_PATH}/testfile.txt"'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_19_verify_testfile2_exist_on_freenas():
    cmd = f'test -f "{SMB_PATH}/testfile2.txt"'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_20_deleting_smb_testfile_on_bsd():
    cmd = f'rm "{MOUNTPOINT}/testfile.txt"'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_21_verify_testfile_is_deleted_on_freenas():
    cmd = f'test -f "{SMB_PATH}/testfile.txt"'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, results['output']


# testing unmount with a testfile2 in smb
@bsd_host_cfg
def test_22_unmounting_smb_on_bsd():
    cmd = f'umount -f {MOUNTPOINT}'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_23_verify_testfile2_exist_on_freenas():
    cmd = f'test -f "{SMB_PATH}/testfile2.txt"'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_24_remounting_smb_on_bsd():
    cmd = f'mount_smbfs -N -I {ip} "//guest@testnas/{SMB_NAME}" "{MOUNTPOINT}"'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_25_verify_testfile2_exist_on_freenas():
    cmd = f'test -f "{SMB_PATH}/testfile2.txt"'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_26_verify_testfile2_exist_on_bsd():
    cmd = f'test -f "{MOUNTPOINT}/testfile2.txt"'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_27_deleting_testfile2_on_bsd_smb():
    cmd = f'rm "{MOUNTPOINT}/testfile2.txt"'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_28_verify_testfile2_does_not_exist_on_freenas():
    cmd = f'test -f "{SMB_PATH}/testfile2.txt"'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, results['output']


@bsd_host_cfg
def test_29_verify_testfile2_does_not_exist_on_bsd():
    cmd = f'test -f "{MOUNTPOINT}/testfile2.txt"'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is False, results['output']


@bsd_host_cfg
def test_30_creating_smb_file_on_bsd():
    cmd = f'touch {MOUNTPOINT}/testfile.txt'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_31_verify_testfile_exist_on_freenas():
    cmd = f'test -f "{SMB_PATH}/testfile2.txt"'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, results['output']


@bsd_host_cfg
def test_32_unmounting_smb_on_bsd():
    cmd = f'umount -f {MOUNTPOINT}'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_33_removing_smb_mountpoint_on_bsd():
    cmd = f'test -d "{MOUNTPOINT}" && rmdir "{MOUNTPOINT}" || exit 0'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_34_verify_testfile_exist_on_freenas_after_unmout():
    cmd = f'test -f "{SMB_PATH}/testfile2.txt"'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, results['output']


def test_35_setting_enable_smb1_to_false():
    payload = {
        "enable_smb1": False
    }
    results = PUT("/smb/", payload)
    assert results.status_code == 200, results.text


def test_36_change_sharing_smd_home_to_true():
    payload = {
        'home': True
    }
    results = PUT(f"/sharing/smb/id/{smb_id}", payload)
    assert results.status_code == 200, results.text


def test_37_verify_smb_getparm_path_homes():
    cmd = 'midclt call smb.getparm path homes'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert results['output'].strip() == f'{SMB_PATH}/%U'


def test_38_stoping_clif_service():
    payload = {"service": "cifs", "service-control": {"onetime": True}}
    results = POST("/service/stop/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_39_checking_if_cifs_is_stop():
    results = GET("/service?service=cifs")
    assert results.json()[0]['state'] == "STOPPED", results.text


# Create tests
def test_40_update_smb():
    payload = {"syslog": False}
    results = PUT("/smb/", payload)
    assert results.status_code == 200, results.text


def test_41_update_cifs_share():
    results = PUT(f"/sharing/smb/id/{smb_id}/", {"home": False})
    assert results.status_code == 200, results.text


def test_42_starting_cifs_service():
    payload = {"service": "cifs", "service-control": {"onetime": True}}
    results = POST("/service/start/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_43_checking_to_see_if_nfs_service_is_running():
    results = GET("/service?service=cifs")
    assert results.json()[0]["state"] == "RUNNING", results.text


# starting ssh test for OSX
@osx_host_cfg
def test_44_create_mount_point_for_smb_on_osx():
    cmd = f'mkdir -p "{MOUNTPOINT}"'
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
def test_45_mount_smb_share_on_osx():
    cmd = f'mount -t smbfs "smb://guest@{ip}/{SMB_NAME}" "{MOUNTPOINT}"'
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
def test_46_verify_testfile_exist_on_osx_mountpoint():
    cmd = f'test -f "{MOUNTPOINT}/testfile.txt"'
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
def test_47_creat_smb_test_file_into_a_tmp_directory_on_osx():
    cmd = f'mkdir -p "{MOUNTPOINT}/tmp"'
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
def test_48_moving_smb_test_file_into_a_tmp_directory_on_osx():
    cmd = f'mv "{MOUNTPOINT}/testfile.txt" "{MOUNTPOINT}/tmp/testfile.txt"'
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
def test_49_deleting_test_file_and_directory_from_smb_share_on_osx():
    cmd = f'rm -f "{MOUNTPOINT}/tmp/testfile.txt" && rmdir "{MOUNTPOINT}/tmp"'
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
def test_49_verifying_test_file_directory_were_successfully_removed_on_osx():
    cmd = f'find -- "{MOUNTPOINT}/" -prune -type d -empty | grep -q .'
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
def test_50_unmount_smb_share_on_osx():
    cmd = f'umount -f "{MOUNTPOINT}"'
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


def test_51_change_timemachine_to_true():
    global vuid
    payload = {
        'timemachine': True,
    }
    results = PUT(f"/sharing/smb/id/{smb_id}/", payload)
    assert results.status_code == 200, results.text
    vuid = results.json()['vuid']


def test_52_verify_that_timemachine_is_true():
    results = GET(f"/sharing/smb/id/{smb_id}/")
    assert results.status_code == 200, results.text
    assert results.json()['timemachine'] is True, results.text


def test_53_verify_smb_getparm_vfs_objects_share():
    cmd = f'midclt call smb.getparm "vfs objects" {SMB_NAME}'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    string_list = '["fruit", "streams_xattr"]'
    assert results['output'].strip() == string_list, results['output']


def test_54_verify_smb_getparm_fruit_volume_uuid_share():
    cmd = f'midclt call smb.getparm "fruit:volume_uuid" {SMB_NAME}'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert results['output'].strip() == vuid, results['output']


def test_55_verify_smb_getparm_fruit_time_machine_is_yes():
    cmd = f'midclt call smb.getparm "fruit:time machine" {SMB_NAME}'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert results['output'].strip() == 'yes', results['output']


def test_60_change_recyclebin_to_true():
    global vuid
    payload = {
        "recyclebin": True,
    }
    results = PUT(f"/sharing/smb/id/{smb_id}", payload)
    assert results.status_code == 200, results.text
    vuid = results.json()['vuid']


def test_61_verify_that_recyclebin_is_true():
    results = GET(f"/sharing/smb/id/{smb_id}/")
    assert results.status_code == 200, results.text
    assert results.json()['recyclebin'] is True, results.text


def test_62_verify_smb_getparm_vfs_objects_share():
    cmd = f'midclt call smb.getparm "vfs objects" {SMB_NAME}'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    string_list = '["fruit", "streams_xattr", "crossrename", "recycle"]'
    assert results['output'].strip() == string_list, results['output']


# Update tests
@osx_host_cfg
def test_63_mount_smb_share_on_osx():
    cmd = f'mount -t smbfs "smb://guest@{ip}/{SMB_NAME}" "{MOUNTPOINT}"'
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
def test_64_create_file_on_smb_share_via_osx_to_test_permissions_on_osx():
    cmd = f'touch "{MOUNTPOINT}/testfile.txt"'
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Move test file to a tmp location on the SMB share
@osx_host_cfg
def test_65_moving_smb_test_file_into_a_tmp_directory_on_osx():
    cmd = f'mkdir -p "{MOUNTPOINT}/tmp" && mv "{MOUNTPOINT}/testfile.txt" ' \
        f'"{MOUNTPOINT}/tmp/testfile.txt"'
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Delete test file and test directory from SMB share
@osx_host_cfg
def test_66_deleting_test_file_and_directory_from_smb_share_on_osx():
    cmd = f'rm -f "{MOUNTPOINT}/tmp/testfile.txt" && rmdir "{MOUNTPOINT}/tmp"'
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
def test_67_verifying_test_file_directory_were_successfully_removed_on_osx():
    cmd = f'find -- "{MOUNTPOINT}/" -prune -type d -empty | grep -q .'
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Clean up mounted SMB share
@osx_host_cfg
def test_68_Unmount_smb_share_on_osx():
    cmd = f'umount -f "{MOUNTPOINT}"'
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
def test_69_Removing_smb_mountpoint_on_osx():
    cmd = f'rmdir "{MOUNTPOINT}"'
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


def test_56_get_smb_sharesec_id_and_set_smb_sharesec_share_acl():
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
def test_57_verify_smb_sharesec_change_for(ae):
    results = GET(f"/smb/sharesec/id/{share_id}/")
    assert results.status_code == 200, results.text
    ae_result = results.json()['share_acl'][0][ae]
    assert ae_result == payload['share_acl'][0][ae], results.text


def test_58_verify_smbclient_127_0_0_1_connection():
    cmd = 'smbclient -NL //127.0.0.1'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert 'TestCifsSMB' in results['output'], results['output']
    assert 'My Test SMB Share' in results['output'], results['output']


def test_59_verify_midclt_call_smb_getparm_access_based_share_enum_is_true():
    cmd = f'midclt call smb.getparm "access based share enum" {SMB_NAME}'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert results['output'].strip() == 'False', results['output']


def test_70_delete_cifs_share():
    results = DELETE(f"/sharing/smb/id/{smb_id}")
    assert results.status_code == 200, results.text


# Now stop the service
def test_71_disable_cifs_service_at_boot():
    results = PUT("/service/id/cifs/", {"enable": False})
    assert results.status_code == 200, results.text


def test_72_checking_to_see_if_clif_service_is_enabled_at_boot():
    results = GET("/service?service=cifs")
    assert results.json()[0]["enable"] is False, results.text


def test_73_stoping_clif_service():
    payload = {"service": "cifs", "service-control": {"onetime": True}}
    results = POST("/service/stop/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_74_checking_if_cifs_is_stop():
    results = GET("/service?service=cifs")
    assert results.json()[0]['state'] == "STOPPED", results.text


# Check destroying a SMB dataset
def test_75_destroying_smb_dataset():
    results = DELETE(f"/pool/dataset/id/{dataset_url}/")
    assert results.status_code == 200, results.text
