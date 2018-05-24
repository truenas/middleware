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
from functions import PUT, POST, GET, SSH_TEST, return_output, DELETE
from functions import POSTNOJSON
from auto_config import ip
from config import *

if "BRIDGEHOST" in locals():
    MOUNTPOINT = "/tmp/iscsi" + BRIDGEHOST
global DEVICE_NAME
DEVICE_NAME = ""
TARGET_NAME = "iqn.1994-09.freenasqa:target0"
Reason = "BRIDGEHOST is missing in ixautomation.conf"
BSDReason = 'BSD host configuration is missing in ixautomation.conf'

mount_test_cfg = pytest.mark.skipif(all(["BRIDGEHOST" in locals(),
                                         "MOUNTPOINT" in locals()
                                         ]) is False, reason=Reason)

bsd_host_cfg = pytest.mark.skipif(all(["BSD_HOST" in locals(),
                                       "BSD_USERNAME" in locals(),
                                       "BSD_PASSWORD" in locals()
                                       ]) is False, reason=BSDReason)


# Create tests
# Add iSCSI initator
def test_01_Add_iSCSI_initiator():
    payload = {"id": 1,
               "iscsi_target_initiator_auth_network": "ALL",
               "iscsi_target_initiator_comment": "",
               "iscsi_target_initiator_initiators": "ALL",
               "iscsi_target_initiator_tag": 1}
    results = POST("/services/iscsi/authorizedinitiator/", payload)
    assert results.status_code == 201, results.text


def test_02_Add_ISCSI_portal():
    payload = {"iscsi_target_portal_ips": ["0.0.0.0:3620"]}
    results = POST("/services/iscsi/portal/", payload)
    assert results.status_code == 201, results.text


# Add iSCSI target
def test_03_Add_ISCSI_target():
    payload = {"iscsi_target_name": TARGET_NAME}
    results = POST("/services/iscsi/target/", payload)
    assert results.status_code == 201


# Add Target to groups
def test_04_Add_target_to_groups():
    payload = '''{"iscsi_target": "1",
               "iscsi_target_authgroup": null,
               "iscsi_target_portalgroup": 1,
               "iscsi_target_initiatorgroup": "1",
               "iscsi_target_authtype": "None",
               "iscsi_target_initialdigest": "Auto"}'''
    results = POSTNOJSON("/services/iscsi/targetgroup/", payload)
    assert results.status_code == 201


# Add iSCSI extent
def test_05_Add_ISCSI_extent():
    payload = {"iscsi_target_extent_type": "File",
               "iscsi_target_extent_name": "extent",
               "iscsi_target_extent_filesize": "50MB",
               "iscsi_target_extent_rpm": "SSD",
               "iscsi_target_extent_path": "/mnt/tank/dataset03/iscsi"}
    results = POST("/services/iscsi/extent/", payload)
    assert results.status_code == 201, results.text


# Associate iSCSI target
def test_06_Associate_ISCSI_target():
    payload = {"id": 1,
               "iscsi_extent": 1,
               "iscsi_lunid": None,
               "iscsi_target": 1}
    results = POST("/services/iscsi/targettoextent/", payload)
    assert results.status_code == 201, results.text


# Enable the iSCSI service
def test_07_Enable_iSCSI_service():
    payload = {"srv_enable": True}
    results = PUT("/services/services/iscsitarget/", payload)
    assert results.status_code == 200, results.text


def test_08_Verify_the_iSCSI_service_is_enabled():
    results = GET("/services/services/iscsitarget/")
    assert results.json()["srv_state"] == "RUNNING", results.text


# when SSH_TEST is functional test using it will need to be added
# Now connect to iSCSI target
@mount_test_cfg
@bsd_host_cfg
def test_09_Connecting_to_iSCSI_target():
    cmd = 'iscsictl -A -p %s:3620 -t %s' % (ip, TARGET_NAME)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_10_Waiting_for_iscsi_connection_before_grabbing_device_name():
    while True:
        SSH_TEST('iscsictl -L', BSD_USERNAME, BSD_PASSWORD,
                 BSD_HOST)
        state = 'cat /tmp/.sshCmdTestStdOut | '
        state += 'awk \'$2 == "%s:3620" {print $3}\'' % ip
        iscsi_state = return_output(state)
        if iscsi_state == "Connected:":
            dev = 'cat /tmp/.sshCmdTestStdOut | '
            dev += 'awk \'$2 == "%s:3620" {print $4}\'' % ip
            iscsi_dev = return_output(dev)
            global DEVICE_NAME
            DEVICE_NAME = iscsi_dev
            assert True
            break
        sleep(3)


@mount_test_cfg
@bsd_host_cfg
def test_11_Format_the_target_volume():
    results = SSH_TEST('newfs "/dev/%s"' % DEVICE_NAME,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_12_Creating_iSCSI_mountpoint():
    results = SSH_TEST('mkdir -p "%s"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_13_Mount_the_target_volume():
    cmd = 'mount "/dev/%s" "%s"' % (DEVICE_NAME, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_14_Creating_file():
    cmd = 'touch "%s/testfile"' % MOUNTPOINT
    # The line under doesn't make sence
    # "umount '${MOUNTPOINT}'; rmdir '${MOUNTPOINT}'"
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_15_Moving_file():
    cmd = 'mv "%s/testfile" "%s/testfile2"' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_16_Copying_file():
    cmd = 'cp "%s/testfile2" "%s/testfile"' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_17_Deleting_file():
    results = SSH_TEST('rm "%s/testfile2"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_18_Unmounting_iSCSI_volume():
    results = SSH_TEST('umount "%s"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_19_Mount_the_target_volume():
    results = SSH_TEST('mount "/dev/%s" "%s"' % (DEVICE_NAME, MOUNTPOINT),
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_20_Creating_45MB_file_to_verify_vzol_size_increase():
    results = SSH_TEST('dd if=/dev/zero of=/tmp/45Mfile.img bs=1M count=45',
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_21_Moving_45MB_file_to_verify_vzol_size_increase():
    results = SSH_TEST('mv /tmp/45Mfile.img "%s/testfile1"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_22_Deleting_file():
    results = SSH_TEST('rm "%s/testfile1"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_23_Unmounting_iSCSI_volume():
    results = SSH_TEST('umount -f "%s"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


# Delete tests
@mount_test_cfg
@bsd_host_cfg
def test_24_Removing_iSCSI_volume_mountpoint():
    results = SSH_TEST('rm -rf "%s"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@mount_test_cfg
@bsd_host_cfg
def test_25_Disconnect_iSCSI_target():
    results = SSH_TEST('iscsictl -R -t %s' % TARGET_NAME,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


# Disable the iSCSI service
def test_26_Disable_iSCSI_service():
    payload = {"srv_enable": False}
    results = PUT("/services/services/iscsitarget/", payload)
    assert results.status_code == 200, results.text


def test_27_Verify_the_iSCSI_service_is_Sdisabled():
    results = GET("/services/services/iscsitarget/")
    assert results.json()["srv_state"] == "STOPPED", results.text


# Remove iSCSI target
def test_28_Delete_iSCSI_target():
    results = DELETE("/services/iscsi/target/1/")
    assert results.status_code == 204, results.text


# Remove iSCSI extent
def test_29_Delete_iSCSI_extent():
    results = DELETE("/services/iscsi/extent/1/")
    assert results.status_code == 204, results.text
