#!/usr/bin/env python3

import pytest
import sys
import os
import enum
from time import sleep
from base64 import b64decode
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET, DELETE
from auto_config import (
    ip,
    pool_name,
    dev_test,
)
from pytest_dependency import depends
from protocols import SMB

reason = 'Skip for testing'
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason=reason)


dataset = f"{pool_name}/smb-proto"
dataset_url = dataset.replace('/', '%2F')
SMB_NAME = "SMBPROTO"
smb_path = "/mnt/" + dataset
guest_path_verification = {
    "user": "shareuser",
    "group": 'wheel',
    "acl": True
}
root_path_verification = {
    "user": "root",
    "group": 'wheel',
    "acl": False
}


class DOSmode(enum.Enum):
    READONLY = 1
    HIDDEN = 2
    SYSTEM = 4
    ARCHIVE = 32


netatalk_metadata = """
AAUWBwACAAAAAAAAAAAAAAAAAAAAAAAAAAgAAAAEAAAAmgAAAAAAAAAIAAABYgAAABAAAAAJAAAA
egAAACAAAAAOAAABcgAAAASAREVWAAABdgAAAAiASU5PAAABfgAAAAiAU1lOAAABhgAAAAiAU1Z+
AAABjgAAAARQTEFQbHRhcAQQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAIbmGsyG5hrOAAAAAKEvSOAAAAAAAAAAAAAAAAAcBAAAAAAAA9xS5YAAAAAAZ
AAAA
"""

parsed_meta = """
QUZQAAAAAQAAAAAAgAAAAFBMQVBsdGFwBBAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAA
"""

apple_kmdlabel = """
8oBNzAaTG04NeBVAT078KCEjrzPrwPTUuZ4MXK1qVRDlBqLATmFSDFO2hXrS5VWsrg1DoZqeX6kF
zDEInIzw2XrZkI9lY3jvMAGXu76QvwrpRGv1G3Ehj+0=
"""

apple_kmditemusertags = """
YnBsaXN0MDCgCAAAAAAAAAEBAAAAAAAAAAEAAAAAAAAAAAAAAAAAAAAJ
"""

AFPXattr = {
    "org.netatalk.Metadata": {
        "smbname": "AFP_AfpInfo",
        "text": netatalk_metadata,
        "bytes": b64decode(netatalk_metadata),
        "smb_text": parsed_meta,
        "smb_bytes": b64decode(parsed_meta)
    },
    "com.apple.metadata:_kMDItemUserTags": {
        "smbname": "com.apple.metadata_kMDItemUserTags",
        "text": apple_kmditemusertags,
        "bytes": b64decode(apple_kmditemusertags)
    },
    "com.apple.metadata:kMDLabel_anemgxoe73iplck2hfuumqxdbu": {
        "smbname": "com.apple.metadatakMDLabel_anemgxoe73iplck2hfuumqxdbu",
        "text": apple_kmdlabel,
        "bytes": b64decode(apple_kmdlabel)
    },
}

SMB_USER = "smbuser"
SMB_PWD = "smb1234"


@pytest.mark.dependency(name="SMB_DATASET_CREATED")
def test_001_creating_smb_dataset(request):
    depends(request, ["pool_04"], scope="session")
    payload = {
        "name": dataset,
        "share_type": "SMB"
    }
    results = POST("/pool/dataset/", payload)
    assert results.status_code == 200, results.text


def test_002_get_next_uid_for_smbuser(request):
    depends(request, ["SMB_DATASET_CREATED"])
    results = GET('/user/get_next_uid/')
    assert results.status_code == 200, results.text
    global next_uid
    next_uid = results.json()


@pytest.mark.dependency(name="SMB_USER_CREATED")
def test_003_creating_shareuser_to_test_acls(request):
    depends(request, ["SMB_DATASET_CREATED"])
    global smbuser_id
    payload = {
        "username": SMB_USER,
        "full_name": "SMB User",
        "group_create": True,
        "password": SMB_PWD,
        "uid": next_uid,
    }
    results = POST("/user/", payload)
    assert results.status_code == 200, results.text
    smbuser_id = results.json()


@pytest.mark.dependency(name="SMB_SHARE_CREATED")
def test_006_creating_a_smb_share_path(request):
    depends(request, ["SMB_DATASET_CREATED"])
    global payload, results, smb_id
    payload = {
        "comment": "SMB Protocol Testing Share",
        "path": smb_path,
        "name": SMB_NAME,
        "auxsmbconf": "zfs_core:base_user_quota = 1G"
    }
    results = POST("/sharing/smb/", payload)
    assert results.status_code == 200, results.text
    smb_id = results.json()['id']


@pytest.mark.dependency(name="SMB_SERVICE_STARTED")
def test_007_starting_cifs_service(request):
    depends(request, ["SMB_SHARE_CREATED"])
    payload = {"service": "cifs"}
    results = POST("/service/start/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_008_checking_to_see_if_smb_service_is_running(request):
    depends(request, ["SMB_SHARE_CREATED"])
    results = GET("/service?service=cifs")
    assert results.json()[0]["state"] == "RUNNING", results.text


@pytest.mark.dependency(name="SHARE_IS_WRITABLE")
def test_009_share_is_writable(request):
    """
    This test creates creates an empty file, sets "delete on close" flag, then
    closes it. NTStatusError should be raised containing failure details
    if we are for some reason unable to access the share.

    This test will fail if smb.conf / smb4.conf does not exist on client / server running test.
    """
    depends(request, ["SMB_SHARE_CREATED"])
    c = SMB()
    c.connect(host=ip, share=SMB_NAME, username=SMB_USER, password=SMB_PWD, smb1=False)
    fd = c.create_file("testfile", "w")
    c.close(fd, True)
    c.disconnect()
