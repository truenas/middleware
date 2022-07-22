#!/usr/bin/env python3

import contextlib
import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST, GET, DELETE, wait_on_job
from auto_config import (
    pool_name,
    dev_test,
)
from protocols import SMB
from pytest_dependency import depends
from utils import create_dataset

reason = 'Skip for testing'
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason=reason)

SMB_USER = "smbacluser"
SMB_PWD = "smb1234"


permset = {
    "READ_DATA": False,
    "WRITE_DATA": False,
    "APPEND_DATA": False,
    "READ_NAMED_ATTRS": False,
    "WRITE_NAMED_ATTRS": False,
    "EXECUTE": False,
    "DELETE_CHILD": False,
    "READ_ATTRIBUTES": False,
    "WRITE_ATTRIBUTES": False,
    "DELETE": False,
    "READ_ACL": False,
    "WRITE_ACL": False,
    "WRITE_OWNER": False,
    "SYNCHRONIZE": True
}

flagset = {
    "FILE_INHERIT": False,
    "DIRECTORY_INHERIT": False,
    "INHERIT_ONLY": False,
    "NO_PROPAGATE_INHERIT": False,
    "INHERITED": False
}


@contextlib.contextmanager
def smb_share(path, options=None):
    results = POST("/sharing/smb/", {
        "path": path,
        **(options or {}),
    })
    assert results.status_code == 200, results.text
    id = results.json()["id"]

    try:
        yield id
    finally:
        result = DELETE(f"/sharing/smb/id/{id}/")
        assert result.status_code == 200, result.text

    assert results.status_code == 200, results.text
    global next_uid
    next_uid = results.json()


def get_windows_sd(share, format="LOCAL"):
    results = POST("/smb/get_remote_acl", {
        "server": "127.0.0.1",
        "share": share,
        "username": SMB_USER,
        "password": SMB_PWD,
        "options": {"output_format": format}
    })
    assert results.status_code == 200, results.text
    return results.json()['acl_data']


def iter_permset(path, share, local_acl):
    smbacl = get_windows_sd(share)
    assert smbacl['acl'][0]['perms'] == permset
    for perm in permset.keys():
        permset[perm] = True
        result = POST("/filesystem/setacl/", {'path': path, "dacl": local_acl})
        assert result.status_code == 200, result.text
        job_status = wait_on_job(result.json(), 180)
        assert job_status["state"] == "SUCCESS", str(job_status["results"])
        smbacl = get_windows_sd(share)
        for ace in smbacl["acl"]:
            if ace["id"] != 666:
                continue

            assert ace["perms"] == permset, f'{perm}: {str(ace)}'


def iter_flagset(path, share, local_acl):
    smbacl = get_windows_sd(share)
    assert smbacl['acl'][0]['flags'] == flagset
    for flag in flagset.keys():
        # we automatically canonicalize entries and so INHERITED shifts to end of list
        flagset[flag] = True
        result = POST("/filesystem/setacl/", {'path': path, "dacl": local_acl})
        assert result.status_code == 200, result.text
        job_status = wait_on_job(result.json(), 180)
        assert job_status["state"] == "SUCCESS", str(job_status["results"])
        smbacl = get_windows_sd(share)
        for ace in smbacl["acl"]:
            if ace["id"] != 666:
                continue

            assert ace["flags"] == flagset, f'{flag}: {str(ace)}'


@pytest.mark.dependency(name="SMB_SERVICE_STARTED")
def test_001_start_smb_service(request):
    payload = {"service": "cifs"}
    results = POST("/service/start/", payload)
    assert results.status_code == 200, results.text

    results = GET("/service?service=cifs")
    assert results.json()[0]["state"] == "RUNNING", results.text


@pytest.mark.dependency(name="SMB_USER_CREATED")
def test_002_creating_shareuser_to_test_acls(request):
    depends(request, ["SMB_SERVICE_STARTED"])
    results = GET('/user/get_next_uid/')
    assert results.status_code == 200, results.text
    global new_id
    new_id = results.json()

    global smbuser_id
    payload = {
        "username": SMB_USER,
        "full_name": "SMB User",
        "group_create": True,
        "password": SMB_PWD,
        "uid": new_id,
    }
    results = POST("/user/", payload)
    assert results.status_code == 200, results.text
    smbuser_id = results.json()


def test_003_test_perms(request):
    """
    This test creates a temporary dataset / SMB share,
    then iterates through all the possible permissions bits
    setting local FS ace for each of them and verifies that
    correct NT ACL bit gets toggled when viewed through SMB
    protocol.
    """
    depends(request, ["SMB_SERVICE_STARTED"])

    ds = 'nfs4acl_perms_smb'
    path = f'/mnt/{pool_name}/{ds}'
    with create_dataset(f'{pool_name}/{ds}', {'share_type': 'SMB'}):
        with smb_share(path, {"name": "PERMS"}):
            result = POST('/filesystem/getacl/', {'path': path, 'simplified': False})
            assert result.status_code == 200, result.text
            the_acl = result.json()['acl']
            new_entry = {
                'perms': permset,
                'flags': flagset,
                'id': 666,
                'type': 'ALLOW',
                'tag': 'USER'
            }

            the_acl.insert(0, new_entry)
            result = POST("/filesystem/setacl/", {'path': path, "dacl": the_acl})
            assert result.status_code == 200, result.text
            job_status = wait_on_job(result.json(), 180)
            assert job_status["state"] == "SUCCESS", str(job_status["results"])
            iter_permset(path, "PERMS", the_acl)


def test_004_test_flags(request):
    """
    This test creates a temporary dataset / SMB share,
    then iterates through all the possible inheritance flags
    setting local FS ace for each of them and verifies that
    correct NT ACL bit gets toggled when viewed through SMB
    protocol.
    """
    depends(request, ["SMB_SERVICE_STARTED"])

    ds = 'nfs4acl_flags_smb'
    path = f'/mnt/{pool_name}/{ds}'
    with create_dataset(f'{pool_name}/{ds}', {'share_type': 'SMB'}):
        with smb_share(path, {"name": "FLAGS"}):
            result = POST('/filesystem/getacl/', {'path': path, 'simplified': False})
            assert result.status_code == 200, result.text
            the_acl = result.json()['acl']
            new_entry = {
                'perms': permset,
                'flags': flagset,
                'id': 666,
                'type': 'ALLOW',
                'tag': 'USER'
            }

            the_acl.insert(0, new_entry)
            result = POST("/filesystem/setacl/", {'path': path, "dacl": the_acl})
            assert result.status_code == 200, result.text
            job_status = wait_on_job(result.json(), 180)
            assert job_status["state"] == "SUCCESS", str(job_status["results"])
            iter_flagset(path, "FLAGS", the_acl)


def test_005_test_map_modify(request):
    """
    This test validates that we are generating an appropriate SD when user has
    'stripped' an ACL from an SMB share. Appropriate in this case means one that
    grants an access mask equaivalent to MODIFY or FULL depending on whether it's
    the file owner or group / other.
    """
    depends(request, ["SMB_SERVICE_STARTED", "pool_04"], scope="session")

    ds = 'nfs4acl_map_modify'
    path = f'/mnt/{pool_name}/{ds}'
    with create_dataset(f'{pool_name}/{ds}', {'aclmode': 'PASSTHROUGH'}, None, 777):
        with smb_share(path, {"name": "MAP_MODIFY"}):
            sd = get_windows_sd("MAP_MODIFY", "SMB")
            dacl = sd['dacl']
            assert dacl[0]['access_mask']['standard'] == 'FULL', str(dacl[0])
            assert dacl[1]['access_mask']['special']['WRITE_ATTRIBUTES'], str(dacl[1])
            assert dacl[1]['access_mask']['special']['WRITE_EA'], str(dacl[1])
            assert dacl[2]['access_mask']['special']['WRITE_ATTRIBUTES'], str(dacl[2])
            assert dacl[2]['access_mask']['special']['WRITE_EA'], str(dacl[2])


def test_007_test_disable_autoinherit(request):
    depends(request, ["SMB_SERVICE_STARTED", "pool_04"], scope="session")
    ds = 'nfs4acl_disable_inherit'
    path = f'/mnt/{pool_name}/{ds}'
    with create_dataset(f'{pool_name}/{ds}', {'share_type': 'SMB'}):
        with smb_share(path, {'name': 'NFS4_INHERIT'}):
            c = SMB()
            c.connect(host=ip, share='NFS4_INHERIT', username=SMB_USER, password=SMB_PWD, smb1=False)
            c.mkdir('foo')
            sd = c.get_sd('foo')
            assert 'SEC_DESC_DACL_PROTECTED' not in sd['control']['parsed'], str(sd)
            c.inherit_acl('foo', 'COPY')
            sd = c.get_sd('foo')
            assert 'SEC_DESC_DACL_PROTECTED' in sd['control']['parsed'], str(sd)
            c.disconnect()


def test_099_delete_smb_user(request):
    depends(request, ["SMB_USER_CREATED"])
    results = DELETE(f"/user/id/{smbuser_id}/", {"delete_group": True})
    assert results.status_code == 200, results.text


def test_100_stop_smb_service(request):
    depends(request, ["SMB_SERVICE_STARTED"])
    payload = {"service": "cifs"}
    results = POST("/service/stop/", payload)
    assert results.status_code == 200, results.text
