#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, GET_OUTPUT, DELETE, SSH_TEST
from config import *

if "BRIDGEHOST" in locals():
    MOUNTPOINT = "/tmp/ad-bsd" + BRIDGEHOST
DATASET = "ad-bsd"
SMB_NAME = "TestShare"
SMB_PATH = "/mnt/tank/" + DATASET
VOL_GROUP = "wheel"

Reason = "BRIDGEHOST, BRIDGEDOMAIN, ADPASSWORD, and ADUSERNAME are missing in "
Reason += "ixautomation.conf"
BSDReason = 'BSD host configuration is missing in ixautomation.conf'

ad_test_cfg = pytest.mark.skipif(all(["BRIDGEHOST" in locals(),
                                      "BRIDGEDOMAIN" in locals(),
                                      "ADPASSWORD" in locals(),
                                      "ADUSERNAME" in locals(),
                                      "MOUNTPOINT" in locals()
                                      ]) is False, reason=Reason)

bsd_host_cfg = pytest.mark.skipif(all(["BSD_HOST" in locals(),
                                       "BSD_USERNAME" in locals(),
                                       "BSD_PASSWORD" in locals()
                                       ]) is False, reason=BSDReason)


@bsd_host_cfg
@ad_test_cfg
def test_01_Removing_SMB_mountpoint():
    cmd = 'test -d "%s" && rmdir "%s" || exit 0' % (MOUNTPOINT, MOUNTPOINT)
    assert SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST) is True


# Disable Active Directory Directory
@ad_test_cfg
def test_02_Disabling_Active_Directory():
    payload = {"ad_bindpw": ADPASSWORD,
               "ad_bindname": ADUSERNAME,
               "ad_domainname": BRIDGEDOMAIN,
               "ad_netbiosname_a": BRIDGEHOST,
               "ad_idmap_backend": "ad",
               "ad_enable": False}
    assert PUT("/directoryservice/activedirectory/1/", payload) == 200


# Check Active Directory
@ad_test_cfg
def test_03_Verify_Active_Directory_is_disabled():
    assert GET_OUTPUT("/directoryservice/activedirectory/",
                      "ad_enable") is False


@ad_test_cfg
def test_04_Verify_SMB_service_is_disabled():
    assert GET_OUTPUT("/services/services/cifs/", "srv_state") == "STOPPED"


# Check destroying a SMB dataset
def test_05_Destroying_SMB_dataset():
    assert DELETE("/storage/volume/1/datasets/%s/" % DATASET) == 204
