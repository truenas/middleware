#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET, DELETE, SSH_TEST, wait_on_job
from functions import dns_service_resolve
from auto_config import ip, pool_name, hostname, ha
from config import *


MOUNTPOINT = f"/tmp/afp-{hostname}"
dataset = f"{pool_name}/afp"
dataset_url = dataset.replace('/', '%2F')
AFP_NAME = "MyAFPShare"
AFP_PATH = f"/mnt/{dataset}"
VOL_GROUP = "wheel"
Reason = "BRIDGEHOST is missing in ixautomation.conf"
OSXReason = 'OSX host configuration is missing in ixautomation.conf'


osx_host_cfg = pytest.mark.skipif(all(["OSX_HOST" in locals(),
                                       "OSX_USERNAME" in locals(),
                                       "OSX_PASSWORD" in locals()
                                       ]) is False, reason=OSXReason)

skip_on_ha = pytest.mark.skipif(ha, reason='Skiping on HA')


# have to wait for the volume api
def test_01_creating_afp_dataset():
    results = POST("/pool/dataset/", {"name": dataset})
    assert results.status_code == 200, results.text


def test_02_changing__dataset_permissions_of_afp_dataset():
    global job_id
    payload = {
        "acl": [],
        "mode": "777",
        "user": "root",
        "group": "wheel"
    }
    results = POST(f"/pool/dataset/id/{dataset_url}/permission/", payload)
    assert results.status_code == 200, results.text
    job_id = results.json()


def test_03_verify_the_job_id_is_successfull():
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_04_get_afp_bindip():
    results = GET("/afp/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert isinstance(results.json()['bindip'], list), results.text


def test_05_setting_afp():
    global payload, results
    payload = {"guest": True,
               "bindip": [ip]}
    results = PUT("/afp/", payload)
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('data', ['guest', 'bindip'])
def test_06_verify_new_setting_afp_for_(data):
    assert results.json()[data] == payload[data], results.text
    assert isinstance(results.json(), dict), results.text


def test_07_get_new_afp_data():
    global results
    results = GET("/afp/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


@pytest.mark.parametrize('data', ['guest', 'bindip'])
def test_08_verify_new_afp_data_for_(data):
    assert results.json()[data] == payload[data], results.text


def test_09_send_empty_afp_data():
    global results
    results = PUT("/afp/", {})
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('data', ['guest', 'bindip'])
def test_10_verify_afp_data_did_not_change_for_(data):
    assert results.json()[data] == payload[data], results.text


def test_11_enable_afp_service_at_boot():
    results = PUT("/service/id/afp/", {"enable": True})
    assert results.status_code == 200, results.text


def test_12_checking_afp_enable_at_boot():
    results = GET("/service?service=afp")
    assert results.json()[0]['enable'] is True, results.text


def test_13_start_afp_service():
    payload = {"service": "afp", "service-control": {"onetime": True}}
    results = POST("/service/start/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_14_checking_if_afp_is_running():
    results = GET("/service?service=afp")
    assert results.json()[0]['state'] == "RUNNING", results.text


@skip_on_ha
def test_15_verify_afp_mdns_service_record():
    results = dns_service_resolve(hostname, 'local', '_afpovertcp._tcp.')
    assert results['status'] is True, str(results['results'])
    assert results['results']['port'] == 548, str(results['results'])


def test_16_creating_a_afp_share_on_afp_path():
    payload = {
        "name": AFP_NAME,
        "path": AFP_PATH,
        "timemachine": True,
    }
    results = POST("/sharing/afp/", payload)
    assert results.status_code == 200, results.text


def test_17_restart_afp_service():
    payload = {"service": "afp", "service-control": {"onetime": True}}
    results = POST("/service/restart/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_18_verify_if_afp_service_is_running_after_restart():
    results = GET("/service?service=afp")
    assert results.json()[0]['state'] == "RUNNING", results.text


@skip_on_ha
def test_19_verify_adisk_mdns_service_record():
    results = dns_service_resolve(hostname, 'local', '_adisk._tcp.')
    assert results['status'] is True, str(results['results'])
    assert results['results']['port'] == 9, str(results['results'])


# have to wait for the volume api
# Mount share on OSX system and create a test file
@osx_host_cfg
def test_20_create_mount_point_for_afp_on_osx_system():
    cmd = f'mkdir -p "{MOUNTPOINT}"'
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
def test_21_mount_afp_share_on_osx_system():
    cmd = f'mount -t afp "afp://{ip}/{AFP_NAME}" "{MOUNTPOINT}"'
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
def test_22_create_file_on_afp_share_via_osx_to_test_permissions():
    cmd = f'touch "{MOUNTPOINT}/testfile.txt"'
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Move test file to a new location on the AFP share
@osx_host_cfg
def test_23_moving_afp_test_file_into_a_new_directory():
    cmd = f'mkdir -p "{MOUNTPOINT}/tmp" && mv "{MOUNTPOINT}/testfile.txt" ' \
        f'"{MOUNTPOINT}/tmp/testfile.txt"'
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Delete test file and test directory from AFP share
@osx_host_cfg
def test_24_deleting_test_file_and_directory_from_afp_share():
    cmd = f'rm -f "{MOUNTPOINT}/tmp/testfile.txt" && rmdir "{MOUNTPOINT}/tmp"'
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
def test_25_verifying_test_file_directory_were_successfully_removed():
    cmd = f'find -- "{MOUNTPOINT}/" -prune -type d -empty | grep -q .'
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Clean up mounted AFP share
@osx_host_cfg
def test_26_unmount_afp_share():
    cmd = f"umount -f '{MOUNTPOINT}'"
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Update test
def test_27_updating_the_apf_service():
    payload = {"connections_limit": 10}
    results = PUT("/afp/", payload)
    assert results.status_code == 200, results.text


def test_28_update_afp_share():
    afpid = GET(f'/sharing/afp?name={AFP_NAME}').json()[0]['id']
    payload = {"home": True, "comment": "AFP Test"}
    results = PUT(f"/sharing/afp/id/{afpid}", payload)
    assert results.status_code == 200, results.text


def test_28_checking_to_see_if_afp_service_is_enabled():
    results = GET("/service?service=afp")
    assert results.json()[0]["state"] == "RUNNING", results.text


# Update tests
@osx_host_cfg
def test_30_mount_afp_share_on_osx_system():
    cmd = f'mount -t afp "afp://{ip}/{AFP_NAME}" "{MOUNTPOINT}"'
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
def test_31_create_file_on_afp_share_via_osx_to_test_permissions():
    cmd = f'touch "{MOUNTPOINT}/testfile.txt"'
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Move test file to a new location on the AFP share
@osx_host_cfg
def test_32_moving_afp_test_file_into_a_new_directory():
    cmd = f'mkdir -p "{MOUNTPOINT}/tmp" && mv "{MOUNTPOINT}/testfile.txt" ' \
        f'"{MOUNTPOINT}/tmp/testfile.txt"'
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Delete test file and test directory from AFP share
@osx_host_cfg
def test_33_deleting_test_file_and_directory_from_afp_share():
    cmd = f'rm -f "{MOUNTPOINT}/tmp/testfile.txt" && rmdir "{MOUNTPOINT}/tmp"'
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


@osx_host_cfg
def test_34_verifying_test_file_directory_were_successfully_removed():
    cmd = f'find -- "{MOUNTPOINT}/" -prune -type d -empty | grep -q .'
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Clean up mounted AFP share
@osx_host_cfg
def test_35_unmount_afp_share():
    cmd = f'umount -f "{MOUNTPOINT}"'
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


# Delete tests
@osx_host_cfg
def test_36_removing_SMB_mountpoint():
    cmd = f'test -d "{MOUNTPOINT}" && rmdir "{MOUNTPOINT}" || exit 0'
    results = SSH_TEST(cmd, OSX_USERNAME, OSX_PASSWORD, OSX_HOST)
    assert results['result'] is True, results['output']


def test_37_delete_afp_share():
    afpid = GET(f'/sharing/afp?name={AFP_NAME}').json()[0]['id']
    results = DELETE(f"/sharing/afp/id/{afpid}")
    assert results.status_code == 200, results.text


def test_38_stopping_afp_service():
    payload = {"service": "afp", "service-control": {"onetime": True}}
    results = POST("/service/stop/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_39_checking_if_afp_is_stop():
    results = GET("/service?service=afp")
    assert results.json()[0]['state'] == "STOPPED", results.text


# Test disable AFP
def test_40_disable_afp_service_at_boot():
    results = PUT("/service/id/afp/", {"enable": False})
    assert results.status_code == 200, results.text


def test_41_checking_afp_disable_at_boot():
    results = GET("/service?service=afp")
    assert results.json()[0]['enable'] is False, results.text


def test_42_destroying_afp_dataset():
    results = DELETE(f"/pool/dataset/id/{dataset_url}/")
    assert results.status_code == 200, results.text
