#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import unittest
import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, GET_OUTPUT, RC_TEST  # , POST
from auto_config import ip

TestName = "create rsync"


class create_rsync_test(unittest.TestCase):

    def test_01_Configuring_rsyncd_service(self):
        assert PUT("/services/rsyncd/", {"rsyncd_port": 873}) == 200

    def test_02_Starting_rsyncd_service(self):
        assert PUT("/services/services/rsync/", {"srv_enable": True}) == 200

    def test_03_Checking_to_see_if_rsync_service_is_enabled(self):
        assert GET_OUTPUT("/services/services/rsync/",
                          "srv_state") == "RUNNING"

#    def test_04_Creating_rsync_resource(self):
#        payload = {"rsyncmod_name": "testmod",
#                   "rsyncmod_path": "/mnt/thank/share" }
#        assert POST("/services/rsyncmod/", payload) == 201

    # Test rsync
    def test_05_Testings_rsync_access(self):
        RC_TEST("rsync -avn %s::testmod" % ip) is True
