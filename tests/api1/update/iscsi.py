#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, GET_OUTPUT, SSH_TEST, return_output
from auto_config import ip
from time import sleep
from config import *

if "BRIDGEHOST" in locals():
    MOUNTPOINT = "/tmp/iscsi" + BRIDGEHOST
global DEVICE_NAME
DEVICE_NAME = ""
DEVICE_NAME_PATH = "/tmp/freenasiscsi"
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


# Enable the iSCSI service
def test_01_Enable_iSCSI_service():
    payload = {"srv_enable": True}
    assert PUT("/services/services/iscsitarget/", payload) == 200


def test_02_Verify_the_iSCSI_service_is_enabled():
    assert GET_OUTPUT("/services/services/iscsitarget/",
                      "srv_state") == "RUNNING"


# Now connect to iSCSI target
@mount_test_cfg
@bsd_host_cfg
def test_03_Connecting_to_iSCSI_target():
    SSH_TEST('iscsictl -A -p %s:3620 -t %s' % (ip, TARGET_NAME),
             BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


@mount_test_cfg
@bsd_host_cfg
def test_04_Waiting_for_iscsi_connection_before_grabbing_device_name():
    while True:
        SSH_TEST('iscsictl -L', BSD_USERNAME, BSD_PASSWORD,
                 BSD_HOST) is True
        state = 'cat /tmp/.sshCmdTestStdOut | '
        state += 'awk \'$2 == "%s:3620" {print $3}\'' % ip
        iscsi_state = return_output(state)
        if iscsi_state == "Connected:":
            dev = 'cat /tmp/.sshCmdTestStdOut | '
            dev += 'awk \'$2 == "%s:3620" {print $4}\'' % ip
            iscsi_dev = return_output(dev)
            global DEVICE_NAME
            DEVICE_NAME = iscsi_dev
            print('using "%s"' % DEVICE_NAME)
            break
        sleep(3)


# Now check if we can mount target create, rename, copy, delete, umount
@mount_test_cfg
@bsd_host_cfg
def test_05_Creating_iSCSI_mountpoint():
    SSH_TEST('mkdir -p "%s"' % MOUNTPOINT,
             BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


@mount_test_cfg
@bsd_host_cfg
def test_06_Mount_the_target_volume():
    SSH_TEST('mount "/dev/%s" "%s"' % (DEVICE_NAME, MOUNTPOINT),
             BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


@mount_test_cfg
@bsd_host_cfg
def test_07_Creating_45MB_file_to_verify_vzol_size_increase():
    SSH_TEST('dd if=/dev/zero of=/tmp/45Mfile.img bs=1M count=45',
             BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


@mount_test_cfg
@bsd_host_cfg
def test_08_Moving_45MB_file_to_verify_vzol_size_increase():
    SSH_TEST('mv /tmp/45Mfile.img "%s/testfile1"' % MOUNTPOINT,
             BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


@mount_test_cfg
@bsd_host_cfg
def test_09_Deleting_file():
    SSH_TEST('rm "%s/testfile1"' % MOUNTPOINT,
             BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


@mount_test_cfg
@bsd_host_cfg
def test_10_Unmounting_iSCSI_volume():
    SSH_TEST('umount -f "%s"' % MOUNTPOINT,
             BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


@mount_test_cfg
@bsd_host_cfg
def test_11_Removing_iSCSI_volume_mountpoint():
    SSH_TEST('rm -rf "%s"' % MOUNTPOINT,
             BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


@mount_test_cfg
@bsd_host_cfg
def test_12_Disconnect_iSCSI_target():
    SSH_TEST('iscsictl -R -t %s' % TARGET_NAME,
             BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


# Disable the iSCSI service
def test_13_Disable_iSCSI_service():
    payload = {"srv_enable": False}
    assert PUT("/services/services/iscsitarget/", payload) == 200


def test_14_Verify_the_iSCSI_service_is_Sdisabled():
    assert GET_OUTPUT("/services/services/iscsitarget/",
                      "srv_state") == "STOPPED"
