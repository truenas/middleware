import os
import sys
apifolder = os.getcwd()
sys.path.append(apifolder)

import contextlib
import subprocess
import threading
import time
import urllib.parse

import pytest
from pytest_dependency import depends
from samba import NTSTATUSError

from auto_config import ip, pool_name, password, user, hostname
from functions import POST, GET, DELETE, wait_on_job
from protocols import SMB


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


def run(command):
    return subprocess.run(command, shell=True, check=True, capture_output=True, encoding="utf-8")


@contextlib.contextmanager
def smb_connection(**kwargs):
    c = SMB()
    c.connect(**kwargs)

    try:
        yield c
    finally:
        c.disconnect()


@pytest.mark.dependency(name="create_dataset")
@pytest.mark.parametrize("attachments_list_mode", ["ALLOW", "DENY"])
def test_pool_dataset_unlock_smb(request, attachments_list_mode):
    depends(request, ["pool_04", "smb_001"], scope="session")
    # Prepare test SMB share
    with dataset("normal") as normal:
        result = POST("/filesystem/setperm/", {'path': f"/mnt/{normal}", "mode": "777"})
        assert result.status_code == 200, result.text
        job_status = wait_on_job(result.json(), 180)
        assert job_status["state"] == "SUCCESS", str(job_status["results"])

        with smb_share("normal", f"/mnt/{normal}"):
            # Create an encrypted SMB share, unlocking which might lead to SMB service interruption
            with dataset("encrypted", passphrase_encryption()) as encrypted:
                with smb_share("encrypted", f"/mnt/{encrypted}"):
                    run(f"touch /mnt/{encrypted}/secret")
                    lock_dataset(encrypted)

                    # Mount test SMB share
                    with smb_connection(host=ip, share="normal") as normal_connection:
                        # Locked share should not be mountable
                        with pytest.raises(NTSTATUSError) as e:
                            with smb_connection(host=ip, share="encrypted"):
                                pass
                        assert "The specified share name cannot be found on the remote server" in e.value.args[1]

                        # While unlocking the dataset, infinitely perform writes to test SMB share
                        # and measure IO times
                        io_times = []
                        stop = threading.Event()
                        stopped = threading.Event()
                        fd = normal_connection.create_file("blob", "w")
                        def thread():
                            while not stop.wait(0.1):
                                start = time.monotonic()
                                normal_connection.write(fd, b"0" * 100000)
                                io_times.append(time.monotonic() - start)

                            stopped.set()

                        try:
                            threading.Thread(target=thread, daemon=True).start()

                            unlock_dataset(encrypted, {"attachments_list_mode": attachments_list_mode})
                        finally:
                            stop.set()

                        assert stopped.wait(1)

                        # Ensure that no service interruption occurred
                        assert len(io_times) > 1
                        assert max(io_times) < 0.1

                    if attachments_list_mode == "ALLOW":
                        # We should still not be able to mount encrypted share as we did not reload attachments
                        with pytest.raises(NTSTATUSError) as e:
                            with smb_connection(host=ip, share="encrypted"):
                                pass
                        assert "The specified share name cannot be found on the remote server" in e.value.args[1]

                    if attachments_list_mode == "DENY":
                        # We should be able to mount encrypted share
                        with smb_connection(host=ip, share="encrypted") as encrypted_connection:
                            assert [x["name"] for x in encrypted_connection.ls("")] == ["secret"]
