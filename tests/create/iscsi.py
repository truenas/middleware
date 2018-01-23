#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import unittest
import sys
import os
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET_OUTPUT, BSD_TEST, return_output
from functions import POSTNOJSON
from auto_config import ip
try:
    from config import BRIDGEHOST
except ImportError:
    exit()

MOUNTPOINT = "/tmp/iscsi" + BRIDGEHOST
global DEVICE_NAME
DEVICE_NAME = ""
TARGET_NAME = "iqn.1994-09.freenasqa:target0"


class iscsi_test(unittest.TestCase):

    # Clean up any leftover items from previous failed runs
    @classmethod
    def setUpClass(inst):
        payload = {"srv_enable": False}
        PUT("/services/services/iscsitarget/", payload)
        BSD_TEST("iscsictl -R -a")
        BSD_TEST('umount -f "%s" &>/dev/null' % MOUNTPOINT)
        BSD_TEST('rm -rf "%s" &>/dev/null' % MOUNTPOINT)

    # Add iSCSI initator
    def test_01_Add_iSCSI_initiator(self):
        payload = {"id": 1,
                   "iscsi_target_initiator_auth_network": "ALL",
                   "iscsi_target_initiator_comment": "",
                   "iscsi_target_initiator_initiators": "ALL",
                   "iscsi_target_initiator_tag": 1}
        assert POST("/services/iscsi/authorizedinitiator/", payload) == 201

    def test_02_Add_ISCSI_portal(self):
        payload = {"iscsi_target_portal_ips": ["0.0.0.0:3620"]}
        assert POST("/services/iscsi/portal/", payload) == 201

    # Add iSCSI target
    def test_03_Add_ISCSI_target(self):
        payload = {"iscsi_target_name": TARGET_NAME}
        assert POST("/services/iscsi/target/", payload) == 201

    # Add Target to groups
    def test_04_Add_target_to_groups(self):
        payload = '''{"iscsi_target": "1",
                   "iscsi_target_authgroup": null,
                   "iscsi_target_portalgroup": 1,
                   "iscsi_target_initiatorgroup": "1",
                   "iscsi_target_authtype": "None",
                   "iscsi_target_initialdigest": "Auto"}'''
        assert POSTNOJSON("/services/iscsi/targetgroup/", payload) == 201

    # Add iSCSI extent
    def test_05_Add_ISCSI_extent(self):
        payload = {"iscsi_target_extent_type": "File",
                   "iscsi_target_extent_name": "extent",
                   "iscsi_target_extent_filesize": "50MB",
                   "iscsi_target_extent_rpm": "SSD",
                   "iscsi_target_extent_path": "/mnt/tank/dataset03/iscsi"}
        assert POST("/services/iscsi/extent/", payload) == 201

    # Associate iSCSI target
    def test_06_Associate_ISCSI_target(self):
        payload = {"id": 1,
                   "iscsi_extent": 1,
                   "iscsi_lunid": None,
                   "iscsi_target": 1}
        assert POST("/services/iscsi/targettoextent/", payload) == 201

    # Enable the iSCSI service
    def test_07_Enable_iSCSI_service(self):
        payload = {"srv_enable": True}
        assert PUT("/services/services/iscsitarget/", payload) == 200

    def test_08_Verify_the_iSCSI_service_is_enabled(self):
        assert GET_OUTPUT("/services/services/iscsitarget/",
                          "srv_state") == "RUNNING"

    # when BSD_TEST is functional test using it will need to be added
    # Now connect to iSCSI target
    def test_09_Connecting_to_iSCSI_target(self):
        cmd = 'iscsictl -A -p %s:3620 -t %s' % (ip, TARGET_NAME)
        assert BSD_TEST(cmd) is True

    def test_10_Waiting_for_iscsi_connection_before_grabbing_device_name(self):
        while True:
            BSD_TEST('iscsictl -L') is True
            state = 'cat /tmp/.bsdCmdTestStdOut | '
            state += 'awk \'$2 == "%s:3620" {print $3}\'' % ip
            iscsi_state = return_output(state)
            if iscsi_state == "Connected:":
                dev = 'cat /tmp/.bsdCmdTestStdOut | '
                dev += 'awk \'$2 == "%s:3620" {print $4}\'' % ip
                iscsi_dev = return_output(dev)
                global DEVICE_NAME
                DEVICE_NAME = iscsi_dev
                break
            sleep(3)

    def test_11_Format_the_target_volume(self):
        assert BSD_TEST('newfs "/dev/%s"' % DEVICE_NAME) is True

    def test_12_Creating_iSCSI_mountpoint(self):
        assert BSD_TEST('mkdir -p "%s"' % MOUNTPOINT) is True

    def test_13_Mount_the_target_volume(self):
        cmd = 'mount "/dev/%s" "%s"' % (DEVICE_NAME, MOUNTPOINT)
        assert BSD_TEST(cmd) is True

    def test_14_Creating_file(self):
        cmd = 'touch "%s/testfile"' % MOUNTPOINT
        # The line under doesn't make sence
        # "umount '${MOUNTPOINT}'; rmdir '${MOUNTPOINT}'"
        assert BSD_TEST(cmd) is True

    def test_15_Moving_file(self):
        cmd = 'mv "%s/testfile" "%s/testfile2"' % (MOUNTPOINT, MOUNTPOINT)
        assert BSD_TEST(cmd) is True

    def test_16_Copying_file(self):
        cmd = 'cp "%s/testfile2" "%s/testfile"' % (MOUNTPOINT, MOUNTPOINT)
        assert BSD_TEST(cmd) is True

    def test_17_Deleting_file(self):
        assert BSD_TEST('rm "%s/testfile2"' % MOUNTPOINT) is True

    def test_18_Unmounting_iSCSI_volume(self):
        assert BSD_TEST('umount "%s"' % MOUNTPOINT) is True

    def test_19_Removing_iSCSI_volume_mountpoint(self):
        assert BSD_TEST('rm -rf "%s"' % MOUNTPOINT) is True

    def test_20_Disconnect_all_targets(self):
        assert BSD_TEST('iscsictl -R -t %s' % TARGET_NAME) is True

    # Disable the iSCSI service
    def test_21_Disable_iSCSI_service(self):
        payload = {"srv_enable": "false"}
        assert PUT("/services/services/iscsitarget/", payload) == 200

    def test_22_Verify_the_iSCSI_service_is_disabled(self):
        assert GET_OUTPUT("/services/services/iscsitarget/",
                          "srv_state") == "STOPPED"

if __name__ == "__main__":
    unittest.main(verbosity=2)
