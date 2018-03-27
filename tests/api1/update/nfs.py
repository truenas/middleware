#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, GET_OUTPUT


def test_01_Updating_the_NFS_service():
    assert PUT("/services/nfs/", {"nfs_srv_servers": "50"}) == 200


def test_02_Checking_to_see_if_NFS_service_is_enabled():
    assert GET_OUTPUT("/services/services/nfs/", "srv_state") == "RUNNING"
