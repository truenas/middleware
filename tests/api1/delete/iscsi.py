#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import DELETE, PUT, BSD_TEST
from config import *

if "BRIDGEHOST" in locals():
    MOUNTPOINT = "/tmp/iscsi" + BRIDGEHOST
DEVICE_NAME_PATH = "/tmp/iscsi_dev_name"
TARGET_NAME = "iqn.freenas:target0"
Reason = "BRIDGEHOST is missing in ixautomation.conf"

mount_test_cfg = pytest.mark.skipif(all(["BRIDGEHOST" in locals(),
                                         "MOUNTPOINT" in locals()
                                         ]) is False, reason=Reason)


# Clean up any leftover items from any previous failed runs
@mount_test_cfg
def test_00_cleanup_tests():
    host = pytest.importorskip("config.BSD_HOST")
    username = pytest.importorskip("config.BSD_USERNAME")
    password = pytest.importorskip("config.BSD_PASSWORD")
    PUT("/services/services/iscsitarget/", {"srv_enable": False})
    BSD_TEST("iscsictl -R -t %s" % TARGET_NAME)
    cmd = 'umount -f "%s" &>/dev/null ; ' % MOUNTPOINT
    cmd += 'rmdir "%s" &>/dev/null' % MOUNTPOINT
    BSD_TEST(cmd, username, password, host)


# Remove iSCSI target
def test_01_Delete_iSCSI_target():
    assert DELETE("/services/iscsi/target/1/") == 204


# Remove iSCSI extent
def test_02_Delete_iSCSI_extent():
    assert DELETE("/services/iscsi/extent/1/") == 204
