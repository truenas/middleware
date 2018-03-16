#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import unittest
import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, GET_OUTPUT, POST

TestName = "create tftp"
TESTFILE_NAME = "tftp-testfile.txt"
TESTFILE_PATH = "/tmp/"


class create_tftp_test(unittest.TestCase):

    def test_01_Creating_dataset_tank_tftproot(self):
        payload = {"name": "tftproot"}
        assert POST("/storage/volume/tank/datasets/", payload) == 201

    def test_02_Setting_permissions_for_TFTP_on_mnt_tank_tftproot(self):
        payload = {"mp_path": "/mnt/tank/tftproot",
                   "mp_acl": "unix",
                   "mp_mode": "777",
                   "mp_user": "nobody",
                   "mp_group": "nobody"}
        assert PUT("/storage/permission/", payload) == 201

    def test_03_Configuring_TFTP_service(self):
        payload = {"tftp_directory": "/mnt/tank/tftproot",
                   "tftp_username": "nobody",
                   "tftp_newfiles": True}
        assert PUT("/services/tftp/", payload) == 200

    def test_04_Starting_TFTP_service(self):
        assert PUT("/services/services/tftp/", {"srv_enable": True}) == 200

    def test_05_Checking_to_see_if_TFTP_service_is_enabled(self):
        assert GET_OUTPUT("/services/services/tftp/", "srv_state") == "RUNNING"
