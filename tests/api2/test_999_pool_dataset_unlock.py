import os
import sys
apifolder = os.getcwd()
sys.path.append(apifolder)

import contextlib
import threading
import time
import urllib.parse

import pytest
from pytest_dependency import depends
from samba import ntstatus, NTSTATUSError

from auto_config import ip, pool_name, password, user, dev_test
from functions import POST, DELETE, SSH_TEST, wait_on_job
from protocols import SMB

# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')


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


@pytest.mark.dependency(name="create_dataset")
@pytest.mark.parametrize("toggle_attachments", [True, False])
def test_pool_dataset_unlock_smb(request, toggle_attachments):
    depends(request, ["pool_04", "smb_001"], scope="session")
    # Prepare test SMB share
    with dataset("normal") as normal:
        with smb_share("normal", f"/mnt/{normal}"):
            # Create an encrypted SMB share, unlocking which might lead to SMB service interruption
            with dataset("encrypted", passphrase_encryption()) as encrypted:
                with smb_share("encrypted", f"/mnt/{encrypted}"):
                    cmd = f"touch /mnt/{encrypted}/secret"
                    results = SSH_TEST(cmd, user, password, ip)
                    assert results['result'] is True, results['output']
                    results = POST("/service/start/", {"service": "cifs"})
                    assert results.status_code == 200, results.text
                    lock_dataset(encrypted)
                    # Mount test SMB share
                    with smb_connection(host=ip, share="normal") as normal_connection:
                        # Locked share should not be mountable
                        with pytest.raises(NTSTATUSError) as e:
                            with smb_connection(host=ip, share="encrypted"):
                                pass
                        assert e.value.args[0] == ntstatus.NT_STATUS_BAD_NETWORK_NAME
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
                            unlock_dataset(encrypted, {"toggle_attachments": toggle_attachments})
                        finally:
                            stop.set()

                        res = stopped.wait(1)
                        assert res

                        # Ensure that no service interruption occurred
                        assert len(io_times) > 1
                        assert max(io_times) < 0.1

                    if toggle_attachments:
                        # We should be able to mount encrypted share
                        with smb_connection(host=ip, share="encrypted") as encrypted_connection:
                            assert [x["name"] for x in encrypted_connection.ls("")] == ["secret"]
                    else:
                        # We should still not be able to mount encrypted share as we did not reload attachments
                        with pytest.raises(NTSTATUSError) as e:
                            with smb_connection(host=ip, share="encrypted"):
                                pass

                        assert e.value.args[0] == ntstatus.NT_STATUS_BAD_NETWORK_NAME
    results = POST("/service/stop/", {"service": "cifs"})
    assert results.status_code == 200, results.text
