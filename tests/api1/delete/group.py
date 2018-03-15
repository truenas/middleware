#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import unittest
import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import DELETE

TestName = "delete group"


class delete_group_test(unittest.TestCase):

    # Delete the testgroup
    def test_01_Delete_group_testgroup_newgroup(self):
        assert DELETE("/account/groups/1/") == 204
