#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import pytest
import sys
import os

apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, GET_OUTPUT, DELETE_ALL, DELETE
from config import *

if "BRIDGEHOST" in locals():
    MOUNTPOINT = "/tmp/ldap-bsd" + BRIDGEHOST

DATASET = "ldap-bsd"
SMB_NAME = "TestShare"
SMB_PATH = "/mnt/tank/" + DATASET
LDAP_USER = 'ldapuser'
VOL_GROUP = "qa"
Reason = "BRIDGEHOST, LDAPBASEDN and LDAPHOSTNAME are missing "
Reason += "in ixautomation.conf"
BSDReason = 'BSD host configuration is missing in ixautomation.conf'

ldap_test_cfg = pytest.mark.skipif(all(["BRIDGEHOST" in locals(),
                                        "LDAPBASEDN" in locals(),
                                        "LDAPHOSTNAME" in locals(),
                                        "MOUNTPOINT" in locals()
                                        ]) is False, reason=Reason)

bsd_host_cfg = pytest.mark.skipif(all(["BSD_HOST" in locals(),
                                       "BSD_USERNAME" in locals(),
                                       "BSD_PASSWORD" in locals()
                                       ]) is False, reason=BSDReason)


@ldap_test_cfg
def test_01_Removing_SMB_share_on_SMB_PATH():
    payload = {"cfs_comment": "My Test SMB Share",
               "cifs_path": SMB_PATH,
               "cifs_name": SMB_NAME,
               "cifs_guestok": "true",
               "cifs_vfsobjects": "streams_xattr"}
    DELETE_ALL("/sharing/cifs/", payload) == 204


# Disable LDAP
@ldap_test_cfg
def test_02_Disabling_LDAPd():
    payload = {"ldap_basedn": LDAPBASEDN2,
               "ldap_binddn": LDAPBINDDN2,
               "ldap_bindpw": LDAPBINDPASSWORD2,
               "ldap_netbiosname_a": BRIDGEHOST,
               "ldap_hostname": LDAPHOSTNAME2,
               "ldap_has_samba_schema": True,
               "ldap_enable": False}
    assert PUT("/directoryservice/ldap/1/", payload) == 200


# Now stop the SMB service
def test_03_Stopping_SMB_service():
    PUT("/services/services/cifs/", {"srv_enable": False}) == 200


# Check LDAP
@ldap_test_cfg
def test_04_Verify_LDAP_is_disabled():
    GET_OUTPUT("/directoryservice/ldap/", "ldap_enable") is False


@ldap_test_cfg
def test_05_Verify_SMB_service_is_disabled():
    GET_OUTPUT("/services/services/cifs/", "srv_state") == "STOPPED"


# Check destroying a SMB dataset
def test_06_Destroying_SMB_dataset():
    DELETE("/storage/volume/1/datasets/%s/" % DATASET) == 204
