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
smb_path = "/mnt/" + dataset
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

path_verification = {
    "user": "shareuser",
    "group": "wheel",
    "acl": True
}


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
        "acl": smb_acl,
        "user": "shareuser",
        "group": "wheel",
    }
    results = POST(f"/pool/dataset/id/{dataset_url}/permission/", payload)
    assert results.status_code == 200, results.text


def test_04_get_filesystem_stat_from_smb_path_and_verify_acl_is_true():
    results = POST('/filesystem/stat/', smb_path)
    assert results.status_code == 200, results.text
    assert results.json()['acl'] is True, results.text


def test_05_starting_cifs_service_at_boot():
    results = PUT("/service/id/cifs/", {"enable": True})
    assert results.status_code == 200, results.text


def test_06_checking_to_see_if_clif_service_is_enabled_at_boot():
    results = GET("/service?service=cifs")
    assert results.json()[0]["enable"] is True, results.text


def test_07_creating_a_smb_share_path():
    global payload, results, smb_id
    payload = {
        "comment": "My Test SMB Share",
        "path": smb_path,
        "home": False,
        "name": SMB_NAME,
        "guestok": True,
    }
    results = POST("/sharing/smb/", payload)
    assert results.status_code == 200, results.text
    smb_id = results.json()['id']


def test_08_verify_if_smb_getparm_path_homes_is_null():
    cmd = 'midclt call smb.getparm path homes'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert results['output'].strip() == 'null'


def test_09_starting_cifs_service():
    payload = {"service": "cifs", "service-control": {"onetime": True}}
    results = POST("/service/start/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_10_checking_to_see_if_nfs_service_is_running():
    results = GET("/service?service=cifs")
    assert results.json()[0]["state"] == "RUNNING", results.text


@bsd_host_cfg
def test_11_creating_smb_mountpoint_on_bsd():
    cmd = f'mkdir -p "{MOUNTPOINT}" && sync'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_12_mounting_smb_on_bsd():
    cmd = f'mount_smbfs -N -I {ip} ' \
        f'"//guest@testnas/{SMB_NAME}" "{MOUNTPOINT}"'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_13_creating_testfile_on_bsd():
    cmd = f"touch {MOUNTPOINT}/testfile.txt"
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_14_verify_testfile_exist_on_freenas():
    cmd = f'test -f "{smb_path}/testfile.txt"'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


@bsd_host_cfg
@pytest.mark.parametrize('stat', list(path_verification.keys()))
def test_15_get_filesystem_stat_from_testfilet_and_verify(stat):
    results = POST('/filesystem/stat/', f'{smb_path}/testfile.txt')
    assert results.status_code == 200, results.text
    assert results.json()[stat] == path_verification[stat], results.text


@bsd_host_cfg
def test_16_moving_smb_file_on_bsd():
    cmd = f'mv {MOUNTPOINT}/testfile.txt {MOUNTPOINT}/testfile2.txt'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_17_verify_testfile_does_not_exist_on_freenas():
    cmd = f'test -f "{smb_path}/testfile.txt"'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, results['output']


def test_18_get_filesystem_stat_from_testfile():
    results = POST('/filesystem/stat/', f'{smb_path}/testfile.txt')
    assert results.status_code == 422, results.text
    message = f"Path {smb_path}/testfile.txt not found"
    assert results.json()['message'] == message, results.text


@bsd_host_cfg
def test_19_verify_testfile2_exist_on_freenas():
    cmd = f'test -f "{smb_path}/testfile2.txt"'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_20_copying_smb_file_on_bsd():
    cmd = f'cp {MOUNTPOINT}/testfile2.txt {MOUNTPOINT}/testfile.txt'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_21_verify_testfile_exist_on_freenas():
    cmd = f'test -f "{smb_path}/testfile.txt"'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_22_verify_testfile2_exist_on_freenas():
    cmd = f'test -f "{smb_path}/testfile2.txt"'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_23_deleting_smb_testfile_on_bsd():
    cmd = f'rm "{MOUNTPOINT}/testfile.txt"'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_21_verify_testfile_is_deleted_on_freenas():
    cmd = f'test -f "{smb_path}/testfile.txt"'
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
    cmd = f'test -f "{smb_path}/testfile2.txt"'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_24_remounting_smb_on_bsd():
    cmd = f'mount_smbfs -N -I {ip} "//guest@testnas/{SMB_NAME}" "{MOUNTPOINT}"'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_25_verify_testfile2_exist_on_freenas():
    cmd = f'test -f "{smb_path}/testfile2.txt"'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_26_verify_testfile2_exist_on_bsd():
    cmd = f'test -f "{MOUNTPOINT}/testfile2.txt"'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_27_create_tmp_directory_on_bsd():
    cmd = f'mkdir "{MOUNTPOINT}/tmp"'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_28_verify__the_tmp_directory_exist_on_freenas():
    cmd = f'test -d {smb_path}/tmp'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_29_moving_testfile2_into_the_tmp_directory_on_bsd():
    cmd = f'mv "{MOUNTPOINT}/testfile2.txt" "{MOUNTPOINT}/tmp/testfile2.txt"'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_30_verify_testfile2_is_in_tmp_directory_on_freenas():
    cmd = f'test -f {smb_path}/tmp/testfile2.txt'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_31_deleting_testfile2_on_bsd_smb():
    cmd = f'rm "{MOUNTPOINT}/tmp/testfile2.txt"'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_32_verify_testfile2_is_erased_from_freenas():
    cmd = f'test -f {smb_path}/tmp/testfile2.txt'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, results['output']


@bsd_host_cfg
def test_33_remove_tmp_directory_on_bsd_smb():
    cmd = f'rmdir "{MOUNTPOINT}/tmp"'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_34_verify_the_tmp_directory_exist_on_freenas():
    cmd = f'test -d {smb_path}/tmp'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, results['output']


@bsd_host_cfg
def test_35_verify_the_mount_directory_is_empty_on_bsd():
    cmd = f'find -- "{MOUNTPOINT}/" -prune -type d -empty | grep -q .'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_36_verify_the_mount_directory_is_empty_on_freenas():
    cmd = f'find -- "{smb_path}/" -prune -type d -empty | grep -q .'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_37_creating_smb_file_on_bsd():
    cmd = f'touch {MOUNTPOINT}/testfile.txt'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_38_verify_testfile_exist_on_freenas():
    cmd = f'test -f "{smb_path}/testfile.txt"'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_39_unmounting_smb_on_bsd():
    cmd = f'umount -f {MOUNTPOINT}'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_40_removing_smb_mountpoint_on_bsd():
    cmd = f'rm -r "{MOUNTPOINT}"'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_41_verify_testfile_exist_on_freenas_after_unmout():
    cmd = f'test -f "{smb_path}/testfile.txt"'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


def test_42_setting_enable_smb1_to_false():
    payload = {
        "enable_smb1": False
    }
    results = PUT("/smb/", payload)
    assert results.status_code == 200, results.text


def test_43_change_sharing_smd_home_to_true():
    payload = {
        'home': True
    }
    results = PUT(f"/sharing/smb/id/{smb_id}", payload)
    assert results.status_code == 200, results.text


def test_44_verify_smb_getparm_path_homes():
    cmd = 'midclt call smb.getparm path homes'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert results['output'].strip() == f'{smb_path}/%U'


def test_45_stoping_clif_service():
    payload = {"service": "cifs", "service-control": {"onetime": True}}
    results = POST("/service/stop/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_46_checking_if_cifs_is_stop():
    results = GET("/service?service=cifs")
    assert results.json()[0]['state'] == "STOPPED", results.text


# Create tests
def test_47_update_smb():
    payload = {"syslog": False}
    results = PUT("/smb/", payload)
    assert results.status_code == 200, results.text


def test_48_update_cifs_share():
    results = PUT(f"/sharing/smb/id/{smb_id}/", {"home": False})
    assert results.status_code == 200, results.text


def test_49_starting_cifs_service():
    payload = {"service": "cifs", "service-control": {"onetime": True}}
    results = POST("/service/start/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_50_checking_to_see_if_nfs_service_is_running():
    results = GET("/service?service=cifs")
    assert results.json()[0]["state"] == "RUNNING", results.text


# starting ssh test for OSX
@osx_host_cfg
def test_51_create_mount_point_for_smb_on_osx():
    cmd = f'mkdir -p "{MOUNTPOINT}"'
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
def test_52_mount_smb_share_on_osx():
    cmd = f'mount -t smbfs "smb://guest@{ip}/{SMB_NAME}" "{MOUNTPOINT}"'
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
def test_53_verify_testfile_exist_on_osx_mountpoint():
    cmd = f'test -f "{MOUNTPOINT}/testfile.txt"'
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
def test_54_create_tmp_directory_on_osx():
    cmd = f'mkdir -p "{MOUNTPOINT}/tmp"'
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
def test_55_verify_tmp_directory_exist_on_freenas():
    cmd = f'test -d "{smb_path}/tmp"'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


@osx_host_cfg
def test_56_moving_smb_test_file_into_a_tmp_directory_on_osx():
    cmd = f'mv "{MOUNTPOINT}/testfile.txt" "{MOUNTPOINT}/tmp/testfile.txt"'
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
def test_57_verify_testfile_is_in_tmp_directory_on_freenas():
    cmd = f'test -f {smb_path}/tmp/testfile.txt'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


@osx_host_cfg
def test_58_deleting_test_file_and_directory_from_smb_share_on_osx():
    cmd = f'rm -f "{MOUNTPOINT}/tmp/testfile.txt" && rmdir "{MOUNTPOINT}/tmp"'
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
def test_59_verifying_test_file_directory_were_successfully_removed_on_osx():
    cmd = f'find -- "{MOUNTPOINT}/" -prune -type d -empty | grep -q .'
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
def test_60_unmount_smb_share_on_osx():
    cmd = f'umount -f "{MOUNTPOINT}"'
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


def test_61_change_timemachine_to_true():
    global vuid
    payload = {
        'timemachine': True,
    }
    results = PUT(f"/sharing/smb/id/{smb_id}/", payload)
    assert results.status_code == 200, results.text
    vuid = results.json()['vuid']


def test_62_verify_that_timemachine_is_true():
    results = GET(f"/sharing/smb/id/{smb_id}/")
    assert results.status_code == 200, results.text
    assert results.json()['timemachine'] is True, results.text


@pytest.mark.parametrize('vfs_object', ["ixnas", "fruit", "streams_xattr"])
def test_63_verify_smb_getparm_vfs_objects_share(vfs_object):
    cmd = f'midclt call smb.getparm "vfs objects" {SMB_NAME}'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert vfs_object in results['output'], results['output']


def test_64_verify_smb_getparm_fruit_volume_uuid_share():
    cmd = f'midclt call smb.getparm "fruit:volume_uuid" {SMB_NAME}'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert results['output'].strip() == vuid, results['output']


def test_65_verify_smb_getparm_fruit_time_machine_is_yes():
    cmd = f'midclt call smb.getparm "fruit:time machine" {SMB_NAME}'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert results['output'].strip() == 'yes', results['output']


def test_66_change_recyclebin_to_true():
    global vuid
    payload = {
        "recyclebin": True,
    }
    results = PUT(f"/sharing/smb/id/{smb_id}", payload)
    assert results.status_code == 200, results.text
    vuid = results.json()['vuid']


def test_67_verify_that_recyclebin_is_true():
    results = GET(f"/sharing/smb/id/{smb_id}/")
    assert results.status_code == 200, results.text
    assert results.json()['recyclebin'] is True, results.text


@pytest.mark.parametrize('vfs_object', ["ixnas", "crossrename", "recycle"])
def test_68_verify_smb_getparm_vfs_objects_share(vfs_object):
    cmd = f'midclt call smb.getparm "vfs objects" {SMB_NAME}'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert vfs_object in results['output'], results['output']


# Update tests
@osx_host_cfg
def test_69_mount_smb_share_on_osx():
    cmd = f'mount -t smbfs "smb://guest@{ip}/{SMB_NAME}" "{MOUNTPOINT}"'
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
def test_70_create_testfile_on_smb_share_via_osx():
    cmd = f'touch "{MOUNTPOINT}/testfile.txt"'
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
def test_71_verify_testfile_exist_on_freenas():
    cmd = f'test -f "{smb_path}/testfile.txt"'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


# Delete test file and test directory from SMB share
@osx_host_cfg
def test_72_deleting_test_file_and_directory_from_smb_share_on_osx():
    cmd = f'rm -f "{MOUNTPOINT}/testfile.txt"'
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
def test_73_verify_recycle_directory_exist_on_freenas():
    cmd = f'test -d "{smb_path}/.recycle"'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


@osx_host_cfg
def test_74_verify_guest_directory_exist_in_recycle_directory_on_freenas():
    cmd = f'test -d "{smb_path}/.recycle/guest"'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


@osx_host_cfg
def test_75_verify_testfile_exist_in_recycle_guest_dirctory_on_freenas():
    cmd = f'test -f "{smb_path}/.recycle/guest/testfile.txt"'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


# Clean up mounted SMB share
@osx_host_cfg
def test_76_Unmount_smb_share_on_osx():
    cmd = f'umount -f "{MOUNTPOINT}"'
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
def test_77_Removing_smb_mountpoint_on_osx():
    cmd = f'rm -r "{MOUNTPOINT}"'
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


def test_78_get_smb_sharesec_id_and_set_smb_sharesec_share_acl():
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
def test_79_verify_smb_sharesec_change_for(ae):
    results = GET(f"/smb/sharesec/id/{share_id}/")
    assert results.status_code == 200, results.text
    ae_result = results.json()['share_acl'][0][ae]
    assert ae_result == payload['share_acl'][0][ae], results.text


def test_80_verify_smbclient_127_0_0_1_connection():
    cmd = 'smbclient -NL //127.0.0.1'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert 'TestCifsSMB' in results['output'], results['output']
    assert 'My Test SMB Share' in results['output'], results['output']


def test_81_verify_midclt_call_smb_getparm_access_based_share_enum_is_true():
    cmd = f'midclt call smb.getparm "access based share enum" {SMB_NAME}'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert results['output'].strip() == 'False', results['output']


def test_82_delete_cifs_share():
    results = DELETE(f"/sharing/smb/id/{smb_id}")
    assert results.status_code == 200, results.text


# Now stop the service
def test_83_disable_cifs_service_at_boot():
    results = PUT("/service/id/cifs/", {"enable": False})
    assert results.status_code == 200, results.text


def test_84_checking_to_see_if_clif_service_is_enabled_at_boot():
    results = GET("/service?service=cifs")
    assert results.json()[0]["enable"] is False, results.text


def test_85_stoping_clif_service():
    payload = {"service": "cifs", "service-control": {"onetime": True}}
    results = POST("/service/stop/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_86_checking_if_cifs_is_stop():
    results = GET("/service?service=cifs")
    assert results.json()[0]['state'] == "STOPPED", results.text


# Check destroying a SMB dataset
def test_87_destroying_smb_dataset():
    results = DELETE(f"/pool/dataset/id/{dataset_url}/")
    assert results.status_code == 200, results.text
