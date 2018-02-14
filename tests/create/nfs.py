#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import unittest
import sys
import os
import xmlrunner
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET_OUTPUT, BSD_TEST
from auto_config import ip, results_xml
try:
    from config import BRIDGEHOST
except ImportError:
    RunTest = False
else:
    MOUNTPOINT = "/tmp/nfs" + BRIDGEHOST
    RunTest = True
TestName = "create nfs"

NFS_PATH = "/mnt/tank/share"


class create_nfs_test(unittest.TestCase):

    # Enable NFS server
    def test_01_Creating_the_NFS_server(self):
        paylaod = {"nfs_srv_bindip": ip,
                   "nfs_srv_mountd_port": 618,
                   "nfs_srv_allow_nonroot": False,
                   "nfs_srv_servers": 10,
                   "nfs_srv_udp": False,
                   "nfs_srv_rpcstatd_port": 871,
                   "nfs_srv_rpclockd_port": 32803,
                   "nfs_srv_v4": False,
                   "nfs_srv_v4_krb": False,
                   "id": 1}
        assert PUT("/services/nfs/", paylaod) == 200

    # Check creating a NFS share
    def test_02_Creating_a_NFS_share_on_NFS_PATH(self):
        paylaod = {"nfs_comment": "My Test Share",
                   "nfs_paths": [NFS_PATH],
                   "nfs_security": "sys"}
        assert POST("/sharing/nfs/", paylaod) == 201

    # Now start the service
    def test_03_Starting_NFS_service(self):
        assert PUT("/services/services/nfs/", {"srv_enable": True}) == 200

    def test_06_Checking_to_see_if_NFS_service_is_enabled(self):
        assert GET_OUTPUT("/services/services/nfs/", "srv_state") == "RUNNING"

    # Now check if we can mount NFS / create / rename / copy / delete / umount
    def test_07_Creating_NFS_mountpoint(self):
        assert BSD_TEST('mkdir -p "%s"' % MOUNTPOINT) is True

    def test_08_Mounting_NFS(self):
        cmd = 'mount_nfs %s:%s %s' % (ip, NFS_PATH, MOUNTPOINT)
        # command below does not make sence
        # "umount '${MOUNTPOINT}' ; rmdir '${MOUNTPOINT}'" "60"
        assert BSD_TEST(cmd) is True

    def test_09_Creating_NFS_file(self):
        cmd = 'touch "%s/testfile"' % MOUNTPOINT
        # 'umount "${MOUNTPOINT}"; rmdir "${MOUNTPOINT}"'
        assert BSD_TEST(cmd) is True

    def test_10_Moving_NFS_file(self):
        cmd = 'mv "%s/testfile" "%s/testfile2"' % (MOUNTPOINT, MOUNTPOINT)
        assert BSD_TEST(cmd) is True

    def test_11_Copying_NFS_file(self):
        cmd = 'cp "%s/testfile2" "%s/testfile"' % (MOUNTPOINT, MOUNTPOINT)
        assert BSD_TEST(cmd) is True

    def test_12_Deleting_NFS_file(self):
        assert BSD_TEST('rm "%s/testfile2"' % MOUNTPOINT) is True

    def test_13_Unmounting_NFS(self):
        assert BSD_TEST('umount "%s"' % MOUNTPOINT) is True

    def test_14_Removing_NFS_mountpoint(self):
        cmd = 'test -d "%s" && rmdir "%s" || exit 0' % (MOUNTPOINT, MOUNTPOINT)
        assert BSD_TEST(cmd) is True


def run_test():
    suite = unittest.TestLoader().loadTestsFromTestCase(create_nfs_test)
    xmlrunner.XMLTestRunner(output=results_xml, verbosity=2).run(suite)

if RunTest is True:
    print('\n\nStarting %s tests...' % TestName)
    run_test()
