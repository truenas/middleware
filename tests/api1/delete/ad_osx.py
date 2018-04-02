#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET_OUTPUT, PUT, DELETE
from config import *

if "BRIDGEHOST" in locals():
    MOUNTPOINT = "/tmp/ad-osx" + BRIDGEHOST
DATASET = "ad-osx"
SMB_NAME = "TestShare"
SMB_PATH = "/mnt/tank/" + DATASET
VOL_GROUP = "wheel"
Reason = "BRIDGEHOST, BRIDGEDOMAIN, ADPASSWORD, and ADUSERNAME are missing in "
Reason += "ixautomation.conf"
OSXReason = 'OSX host configuration is missing in ixautomation.conf'

ad_test_cfg = pytest.mark.skipif(all(["BRIDGEHOST" in locals(),
                                      "BRIDGEDOMAIN" in locals(),
                                      "ADPASSWORD" in locals(),
                                      "ADUSERNAME" in locals(),
                                      "MOUNTPOINT" in locals()
                                      ]) is False, reason=Reason)

osx_host_cfg = pytest.mark.skipif(all(["OSX_HOST" in locals(),
                                       "OSX_USERNAME" in locals(),
                                       "OSX_PASSWORD" in locals()
                                       ]) is False, reason=OSXReason)


# Disable Active Directory Directory
@ad_test_cfg
def test_01_Disabling_Active_Directory():
    payload = {"ad_bindpw": ADPASSWORD,
               "ad_bindname": ADUSERNAME,
               "ad_domainname": BRIDGEDOMAIN,
               "ad_netbiosname_a": BRIDGEHOST,
               "ad_idmap_backend": "rid",
               "ad_enable": False}
    assert PUT("/directoryservice/activedirectory/1/", payload) == 200


# Check Active Directory
@ad_test_cfg
def test_02_Verify_Active_Directory_is_disabled():
    assert GET_OUTPUT("/directoryservice/activedirectory/",
                      "ad_enable") is False


@ad_test_cfg
def test_03_Verify_SMB_service_is_disabled():
    assert GET_OUTPUT("/services/services/cifs/", "srv_state") == "STOPPED"


# Check destroying a SMB dataset
def test_04_Destroying_SMB_dataset():
    assert DELETE("/storage/volume/1/datasets/%s/" % DATASET) == 204
