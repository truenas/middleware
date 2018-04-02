#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, DELETE, DELETE_ALL
from config import *

if "BRIDGEHOST" in locals():
    MOUNTPOINT = "/tmp/afp-osx" + BRIDGEHOST
DATASET = "afp-osx"
AFP_NAME = "MyAFPShare"
AFP_PATH = "/mnt/tank/" + DATASET
VOL_GROUP = "wheel"
Reason = "BRIDGEHOST is missing in ixautomation.conf"
OSXReason = 'OSX host configuration is missing in ixautomation.conf'

mount_test_cfg = pytest.mark.skipif(all(["BRIDGEHOST" in locals(),
                                         "MOUNTPOINT" in locals()
                                         ]) is False, reason=Reason)

osx_host_cfg = pytest.mark.skipif(all(["OSX_HOST" in locals(),
                                       "OSX_USERNAME" in locals(),
                                       "OSX_PASSWORD" in locals()
                                       ]) is False, reason=OSXReason)


# Test disable AFP
def test_01_Verify_AFP_service_can_be_disabled():
    assert PUT("/services/afp/", {"afp_srv_guest": "false"}) == 200


def test_02_Verify_delete_afp_name_and_afp_path():
    payload = {"afp_name": AFP_NAME, "afp_path": AFP_PATH}
    assert DELETE_ALL("/sharing/afp/", payload) == 204


# Test delete AFP dataset
def test_03_Verify_AFP_dataset_can_be_destroyed():
    assert DELETE("/storage/volume/1/datasets/%s/" % DATASET) == 204
