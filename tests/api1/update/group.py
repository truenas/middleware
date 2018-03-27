#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT

GroupIdFile = "/tmp/.ixbuild_test_groupid"


# Get the ID of testgroup
def test_01_Fetching_group_id_of_previously_created_test_group():
    if os.path.exists(GroupIdFile):
        global groupid
        groupid = open(GroupIdFile).readlines()[0].rstrip()
        assert True
    else:
        assert False


# Update the testgroup
def test_02_Updating_group_testgroup():
    payload = {"bsdgrp_gid": "1201",
               "bsdgrp_group": "newgroup"}
    assert PUT("/account/groups/%s/" % groupid, payload) == 200
