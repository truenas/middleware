#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import DELETE, GET_USER


def test_00_cleanup_tests():
    global userid
    userid = GET_USER("testuser")


# Delete the testuser
def test_01_Deleting_user_testuser():
    assert DELETE("/account/users/%s/" % userid) == 204
