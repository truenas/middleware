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

from functions import POST, GET, DELETE, wait_on_job
from auto_config import ip, pool_name, password, user, hostname


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


@pytest.mark.dependency(name="create_dataset")
@pytest.mark.parametrize("attachments_list_mode", ["ALLOW", "DENY"])
def test_pool_dataset_unlock_smb(request, attachments_list_mode):
    depends(request, ["pool_04", "smb_001"], scope="session")
    # Prepare test SMB share
    with dataset("normal") as normal:
        os.chmod(f"/mnt/{normal}", 0o777)
        with smb_share("normal", f"/mnt/{normal}"):
            # Create an encrypted SMB share, unlocking which might lead to SMB service interruption
            with dataset("encrypted", passphrase_encryption()) as encrypted:
                with smb_share("encrypted", f"/mnt/{encrypted}"):
                    run(f"touch /mnt/{encrypted}/secret")
                    lock_dataset(encrypted)

                    # Mount test SMB share
                    os.makedirs("/tmp/smb1", exist_ok=True)
                    os.makedirs("/tmp/smb2", exist_ok=True)
                    try:
                        run(f"mount -t cifs -o guest //{ip}/normal /tmp/smb1")

                        # Locked share should not be mountable
                        try:
                            run(f"mount -t cifs -o guest //{ip}/encrypted /tmp/smb2")
                        except subprocess.CalledProcessError as e:
                            assert "No such file or directory" in e.stderr
                        else:
                            assert False

                        # While unlocking the dataset, infinitely perform writes to test SMB share
                        # and measure IO times
                        io_times = []
                        stop = threading.Event()
                        stopped = threading.Event()
                        with open("/tmp/smb1/blob", "w") as f:
                            def thread():
                                while not stop.wait(0.1):
                                    start = time.monotonic()
                                    f.write("0" * 100000)
                                    f.flush()
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
                    finally:
                        run("umount /tmp/smb1")

                    if attachments_list_mode == "ALLOW":
                        # We should still not be able to mount encrypted share as we did not reload attachments
                        try:
                            run(f"mount -t cifs -o guest //{ip}/encrypted /tmp/smb2")
                        except subprocess.CalledProcessError as e:
                            assert "No such file or directory" in e.stderr
                        else:
                            assert False

                    if attachments_list_mode == "DENY":
                        # We should be able to mount encrypted share
                        try:
                            run(f"mount -t cifs -o guest //{ip}/encrypted /tmp/smb2")
                            assert os.path.exists("/tmp/smb2/secret")
                        finally:
                            run("umount /tmp/smb2")
