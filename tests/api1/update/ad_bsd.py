#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET_OUTPUT, SSH_TEST, GET
from auto_config import ip
from config import *

if "BRIDGEHOST" in locals():
    MOUNTPOINT = "/tmp/ad-bsd" + BRIDGEHOST
DATASET = "ad-bsd"
SMB_NAME = "TestShare"
SMB_PATH = "/mnt/tank/" + DATASET
VOL_GROUP = "wheel"

Reason = "BRIDGEHOST, BRIDGEDOMAIN, ADPASSWORD, and ADUSERNAME are missing in "
Reason += "ixautomation.conf"
BSDReason = 'BSD host configuration is missing in ixautomation.conf'

ad_test_cfg = pytest.mark.skipif(all(["BRIDGEHOST" in locals(),
                                      "BRIDGEDOMAIN" in locals(),
                                      "ADPASSWORD" in locals(),
                                      "ADUSERNAME" in locals(),
                                      "MOUNTPOINT" in locals()
                                      ]) is False, reason=Reason)

bsd_host_cfg = pytest.mark.skipif(all(["BSD_HOST" in locals(),
                                       "BSD_USERNAME" in locals(),
                                       "BSD_PASSWORD" in locals()
                                       ]) is False, reason=BSDReason)


# Check destroying a SMB dataset
def test_01_look_for_dataset():
    assert GET("/storage/volume/1/datasets/%s/" % DATASET) == 200


# Check Active Directory
@ad_test_cfg
def test_02_Checking_Active_Directory():
    assert GET_OUTPUT("/directoryservice/activedirectory/",
                      "ad_enable") is True


@ad_test_cfg
def test_03_Checking_to_see_if_SMB_service_is_enabled():
    assert GET_OUTPUT("/services/services/cifs/", "srv_state") == "RUNNING"


# The ADUSER user must exist in AD with this password
@bsd_host_cfg
@ad_test_cfg
def test_05_Store_AD_credentials_in_a_file_for_mount_smbfs():
    cmd = 'echo "[TESTNAS:ADUSER]" > ~/.nsmbrc && '
    cmd += 'echo "password=12345678" >> ~/.nsmbrc'
    assert SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


@ad_test_cfg
def test_06_Mounting_SMB():
    cmd = 'mount_smbfs -N -I %s -W AD01 ' % ip
    cmd += '"//aduser@testnas/%s" "%s"' % (SMB_NAME, MOUNTPOINT)
    assert SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


@bsd_host_cfg
@ad_test_cfg
def test_07_Creating_SMB_file():
    assert SSH_TEST('touch "%s/testfile"' % MOUNTPOINT,
                    BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


@bsd_host_cfg
@ad_test_cfg
def test_08_Moving_SMB_file():
    cmd = 'mv "%s/testfile" "%s/testfile2"' % (MOUNTPOINT, MOUNTPOINT)
    assert SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


@bsd_host_cfg
@ad_test_cfg
def test_09_Copying_SMB_file():
    cmd = 'cp "%s/testfile2" "%s/testfile"' % (MOUNTPOINT, MOUNTPOINT)
    assert SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


@bsd_host_cfg
@ad_test_cfg
def test_10_Deleting_SMB_file_1_2():
    assert SSH_TEST('rm "%s/testfile"' % MOUNTPOINT,
                    BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


@bsd_host_cfg
@ad_test_cfg
def test_11_Deleting_SMB_file_2_2():
    assert SSH_TEST('rm "%s/testfile2"' % MOUNTPOINT,
                    BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


@ad_test_cfg
def test_12_Unmounting_SMB():
    assert SSH_TEST('umount "%s"' % MOUNTPOINT,
                    BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


@bsd_host_cfg
@ad_test_cfg
def test_13_Removing_SMB_mountpoint():
    cmd = 'test -d "%s" && rmdir "%s" || exit 0' % (MOUNTPOINT, MOUNTPOINT)
    assert SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True
