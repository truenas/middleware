#!/usr/bin/env python3

import pytest
import sys
import os
import enum
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET, DELETE, SSH_TEST, wait_on_job
from auto_config import ip, pool_name, password, user, scale, hostname
from pytest_dependency import depends
from protocols import SMB

dataset = f"{pool_name}/smb-proto"
dataset_url = dataset.replace('/', '%2F')
SMB_NAME = "SMBPROTO"
smb_path = "/mnt/" + dataset
group = 'root' if scale else 'wheel'


guest_path_verification = {
    "user": "shareuser",
    "group": group,
    "acl": True
}


root_path_verification = {
    "user": "root",
    "group": group,
    "acl": False
}


class DOSmode(enum.Enum):
    READONLY = 1
    HIDDEN = 2
    SYSTEM = 4
    ARCHIVE = 32


SMB_USER = "smbuser"
SMB_PWD = "smb1234"


@pytest.mark.dependency(name="SMB_DATASET_CREATED")
def test_001_creating_smb_dataset():
    payload = {
        "name": dataset,
        "share_type": "SMB"
    }
    results = POST("/pool/dataset/", payload)
    assert results.status_code == 200, results.text


def test_002_get_next_uid_for_smbuser():
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
        "shell": "/bin/csh"}
    results = POST("/user/", payload)
    assert results.status_code == 200, results.text
    smbuser_id = results.json()


def test_004_changing_dataset_permissions_of_smb_dataset(request):
    depends(request, ["SMB_USER_CREATED"])
    global job_id
    payload = {
        "acl": [],
        "mode": 777,
        "user": SMB_USER,
        "group": group,
    }
    results = POST(f"/pool/dataset/id/{dataset_url}/permission/", payload)
    assert results.status_code == 200, results.text
    job_id = results.json()


@pytest.mark.dependency(name="SMB_PERMISSION_SET")
def test_005_verify_the_job_id_is_successful(request):
    depends(request, ["SMB_USER_CREATED"])
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


@pytest.mark.dependency(name="SMB_SHARE_CREATED")
def test_006_creating_a_smb_share_path(request):
    depends(request, ["SMB_PERMISSION_SET"])
    global payload, results, smb_id
    payload = {
        "comment": "SMB Protocol Testing Share",
        "path": smb_path,
        "name": SMB_NAME,
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


@pytest.mark.parametrize('dm', DOSmode)
def test_010_check_dosmode_create(request, dm):
    """
    This tests the setting of different DOS attributes through SMB2 Create.
    after setting
    """
    depends(request, ["SHARE_IS_WRITABLE"])
    if dm.value > DOSmode.SYSTEM.value:
        return

    c = SMB()
    c.connect(host=ip, share=SMB_NAME, username=SMB_USER, password=SMB_PWD, smb1=False)
    if dm == DOSmode.READONLY:
        fd = c.create_file(dm.name, "w", "r")
    elif dm == DOSmode.HIDDEN:
        fd = c.create_file(dm.name, "w", "h")
    elif dm == DOSmode.SYSTEM:
        fd = c.create_file(dm.name, "w", "s")
    dir_listing = c.ls("/")
    for f in dir_listing:
        if f['name'] != dm.name:
            continue
        # Archive is automatically set by kernel
        to_check = f['attrib'] & ~DOSmode.ARCHIVE.value
        c.disconnect()
        assert (to_check & dm.value) != 0, f


def test_011_check_dos_ro_cred_handling(request):
    """
    This test creates a file with readonly attribute set, then
    uses the open fd to write data to the file.
    """
    depends(request, ["SHARE_IS_WRITABLE"])
    c = SMB()
    c.connect(host=ip, share=SMB_NAME, username=SMB_USER, password=SMB_PWD, smb1=False)
    fd = c.create_file("RO_TEST", "w", "r")
    c.write(fd, b"TESTING123\n")
    c.disconnect()


@pytest.mark.dependency(name="SMB1_ENABLED")
def test_050_enable_smb1(request):
    depends(request, ["SMB_SHARE_CREATED"])
    payload = {
        "enable_smb1": True,
    }
    results = PUT("/smb/", payload)
    assert results.status_code == 200, results.text


@pytest.mark.dependency(name="SHARE_IS_WRITABLE_SMB1")
def test_051_share_is_writable_smb1(request):
    """
    This test creates creates an empty file, sets "delete on close" flag, then
    closes it. NTStatusError should be raised containing failure details
    if we are for some reason unable to access the share.

    This test will fail if client min protocol != NT1 in smb.conf of SMB client.
    Sample smb.conf entry:

    [global]
    client min protocol = nt1
    """
    depends(request, ["SMB_SHARE_CREATED"])
    c = SMB()
    c.connect(host=ip, share=SMB_NAME, username=SMB_USER, password=SMB_PWD, smb1=True)
    fd = c.create_file("testfile", "w")
    c.close(fd, True)
    c.disconnect()


@pytest.mark.parametrize('dm', DOSmode)
def test_052_check_dosmode_create_smb1(request, dm):
    """
    This tests the setting of different DOS attributes through SMB1 create.
    after setting
    """
    depends(request, ["SHARE_IS_WRITABLE"])
    if dm.value > DOSmode.SYSTEM.value:
        return

    c = SMB()
    c.connect(host=ip, share=SMB_NAME, username=SMB_USER, password=SMB_PWD, smb1=True)
    if dm == DOSmode.READONLY:
        fd = c.create_file(f'{dm.name}_smb1', "w", "r")
    elif dm == DOSmode.HIDDEN:
        fd = c.create_file(f'{dm.name}_smb1', "w", "h")
    elif dm == DOSmode.SYSTEM:
        fd = c.create_file(f'{dm.name}_smb1', "w", "s")
    dir_listing = c.ls("/")
    for f in dir_listing:
        if f['name'] != f'{dm.name}_smb1':
            continue
        # Archive is automatically set by kernel
        to_check = f['attrib'] & ~DOSmode.ARCHIVE.value
        c.disconnect()
        assert (to_check & dm.value) != 0, f


def test_100_delete_smb_user(request):
    depends(request, ["SMB_USER_CREATED"])
    results = DELETE(f"/user/id/{smbuser_id}/", {"delete_group": True})
    assert results.status_code == 200, results.text


def test_101_delete_smb_share(request):
    depends(request, ["SMB_SHARE_CREATED"])
    results = DELETE(f"/sharing/smb/id/{smb_id}")
    assert results.status_code == 200, results.text


def test_102_disable_smb1(request):
    depends(request, ["SMB1_ENABLED"])
    payload = {
        "enable_smb1": False,
    }
    results = PUT("/smb/", payload)
    assert results.status_code == 200, results.text


def test_103_stopping_smb_service(request):
    depends(request, ["SMB_SERVICE_STARTED"])
    payload = {"service": "cifs"}
    results = POST("/service/stop/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_104_checking_if_smb_is_stoped(request):
    depends(request, ["SMB_SERVICE_STARTED"])
    results = GET("/service?service=cifs")
    assert results.json()[0]['state'] == "STOPPED", results.text


def test_105_destroying_smb_dataset(request):
    depends(request, ["SMB_DATASET_CREATED"])
    results = DELETE(f"/pool/dataset/id/{dataset_url}/")
    assert results.status_code == 200, results.text
