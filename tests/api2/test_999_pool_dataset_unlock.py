import os
import sys
apifolder = os.getcwd()
sys.path.append(apifolder)

import contextlib
import urllib.parse

import pytest

from auto_config import pool_name
from functions import POST, DELETE, wait_on_job
from middlewared.test.integration.assets.account import user
from middlewared.test.integration.utils import call, ssh
from protocols import SMB
from samba import ntstatus, NTSTATUSError


SMB_PASSWORD = 'Abcd1234'
SMB_USER = 'smbuser999'


def passphrase_encryption():
    return {
        'encryption_options': {
            'generate_key': False,
            'pbkdf2iters': 100000,
            'algorithm': 'AES-128-CCM',
            'passphrase': 'passphrase',
        },
        'encryption': True,
        'inherit_encryption': False,
    }


@contextlib.contextmanager
def dataset(name, options=None):
    assert "/" not in name

    dataset = f"{pool_name}/{name}"

    result = POST("/pool/dataset/", {"name": dataset, **(options or {})})
    assert result.status_code == 200, result.text

    result = POST("/filesystem/setperm/", {'path': f"/mnt/{dataset}", "mode": "777"})
    assert result.status_code == 200, result.text
    job_status = wait_on_job(result.json(), 180)
    assert job_status["state"] == "SUCCESS", str(job_status["results"])

    try:
        yield dataset
    finally:
        result = DELETE(f"/pool/dataset/id/{urllib.parse.quote(dataset, '')}/")
        assert result.status_code == 200, result.text


@contextlib.contextmanager
def smb_share(name, path, options=None):
    results = POST("/sharing/smb/", {
        "name": name,
        "path": path,
        "guestok": True,
        **(options or {}),
    })
    assert results.status_code == 200, results.text
    id = results.json()["id"]

    try:
        yield id
    finally:
        result = DELETE(f"/sharing/smb/id/{id}/")
        assert result.status_code == 200, result.text


def lock_dataset(name):
    payload = {
        'id': name,
        'lock_options': {
            'force_umount': True
        }
    }
    results = POST('/pool/dataset/lock', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 120)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def unlock_dataset(name, options=None):
    payload = {
        'id': name,
        'unlock_options': {
            'recursive': True,
            'datasets': [
                {
                    'name': name,
                    'passphrase': 'passphrase'
                }
            ],
            **(options or {}),
        }
    }
    results = POST('/pool/dataset/unlock/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 120)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    assert job_status['results']['result']['unlocked'] == [name], str(job_status['results'])


@contextlib.contextmanager
def smb_connection(**kwargs):
    c = SMB()
    c.connect(**kwargs)

    try:
        yield c
    finally:
        c.disconnect()


@pytest.fixture(scope='module')
def smb_user():
    with user({
        'username': SMB_USER,
        'full_name': 'doug',
        'group_create': True,
        'password': SMB_PASSWORD,
        'smb': True
    }, get_instance=True) as u:
        yield u


@pytest.mark.dependency(name="create_dataset")
@pytest.mark.parametrize("toggle_attachments", [True, False])
def test_pool_dataset_unlock_smb(smb_user, toggle_attachments):
    # Prepare test SMB share
    with dataset("normal") as normal:
        with smb_share("normal", f"/mnt/{normal}"):
            # Create an encrypted SMB share, unlocking which might lead to SMB service interruption
            with dataset("encrypted", passphrase_encryption()) as encrypted:
                with smb_share("encrypted", f"/mnt/{encrypted}"):
                    ssh(f"touch /mnt/{encrypted}/secret")
                    results = POST("/service/start/", {"service": "cifs"})
                    assert results.status_code == 200, results.text
                    lock_dataset(encrypted)
                    # Mount test SMB share
                    with smb_connection(
                        share="normal",
                        username=SMB_USER,
                        password=SMB_PASSWORD
                    ) as normal_connection:
                        # Locked share should not be mountable
                        with pytest.raises(NTSTATUSError) as e:
                            with smb_connection(
                                share="encrypted",
                                username=SMB_USER,
                                password=SMB_PASSWORD
                            ):
                                pass

                        assert e.value.args[0] == ntstatus.NT_STATUS_BAD_NETWORK_NAME

                        conn = normal_connection.show_connection()
                        assert conn['connected'], conn
                        unlock_dataset(encrypted, {"toggle_attachments": toggle_attachments})

                        conn = normal_connection.show_connection()
                        assert conn['connected'], conn

                    if toggle_attachments:
                        # We should be able to mount encrypted share
                        with smb_connection(
                            share="encrypted",
                            username=SMB_USER,
                            password=SMB_PASSWORD
                        ) as encrypted_connection:
                            assert [x["name"] for x in encrypted_connection.ls("")] == ["secret"]
                    else:
                        # We should still not be able to mount encrypted share as we did not reload attachments
                        with pytest.raises(NTSTATUSError) as e:
                            with smb_connection(
                                share="encrypted",
                                username=SMB_USER,
                                password=SMB_PASSWORD
                            ):
                                pass

                        assert e.value.args[0] == ntstatus.NT_STATUS_BAD_NETWORK_NAME
    assert call("service.stop", "cifs")
