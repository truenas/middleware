#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST, PUT, DELETE

GroupIdFile = "/tmp/.ixbuild_test_groupid"


# Create tests
def test_01_Creating_group_testgroup():
    payload = {"bsdgrp_gid": 1200, "bsdgrp_group": "testgroup"}
    results = POST("/account/groups/", payload)
    assert results.status_code == 201, results.text


# Update tests
# Get the ID of testgroup
# def test_01_Fetching_group_id_of_previously_created_test_group():
#     if os.path.exists(GroupIdFile):
#         global groupid
#         groupid = open(GroupIdFile).readlines()[0].rstrip()
#         assert True
#     else:
#         assert False


# Update the testgroup
# def test_02_Updating_group_testgroup():
#     payload = {"bsdgrp_gid": "1201",
#                "bsdgrp_group": "newgroup"}
#     assert PUT("/account/groups/%s/" % groupid, payload) == 200


# Delete tests
# Delete the testgroup
# def test_01_Delete_group_testgroup_newgroup():
#     assert DELETE("/account/groups/1/") == 204
