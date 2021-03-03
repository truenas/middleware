#!/usr/bin/env python3

import pytest
import sys
import os
import time
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST, GET, DELETE, SSH_TEST, send_file
from auto_config import ip, user, password, pool_name, scale, ha
from auto_config import dev_test
reason = 'Skip for testing' if dev_test else 'Skipping test for HA'
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(ha or dev_test, reason=reason)

dataset = f"{pool_name}/test_pool"
dataset_url = dataset.replace('/', '%2F')
dataset_path = os.path.join("/mnt", dataset)

IMAGES = {}
loops = {
    'msdosfs': '/dev/loop8',
    'msdosfs-nonascii': '/dev/loop9',
    'ntfs': '/dev/loop10'
}


def expect_state(job_id, state):
    for _ in range(60):
        job = GET(f"/core/get_jobs/?id={job_id}").json()[0]
        if job["state"] in ["WAITING", "RUNNING"]:
            time.sleep(1)
            continue
        if job["state"] == state:
            return job
        else:
            assert False, str(job)
    assert False, str(job)


def test_01_create_dataset(request):
    depends(request, ["pool_04"], scope="session")
    result = POST("/pool/dataset/", {"name": dataset})
    assert result.status_code == 200, result.text


@pytest.mark.parametrize('image', ["msdosfs", "msdosfs-nonascii", "ntfs"])
def test_02_setup_function(request, image):
    depends(request, ["pool_04", "ssh_key"], scope="session")
    zf = os.path.join(os.path.dirname(__file__), "fixtures", f"{image}.gz")
    destination = f"/tmp/{image}.gz"
    send_results = send_file(zf, destination, user, None, ip)
    assert send_results['result'] is True, send_results['output']

    cmd = f"gunzip -f /tmp/{image}.gz"
    gunzip_results = SSH_TEST(cmd, user, password, ip)
    assert gunzip_results['result'] is True, gunzip_results['output']
    if scale is True:
        cmd = f"losetup -P {loops[image]} /tmp/{image}"
    else:
        cmd = f"mdconfig -a -t vnode -f /tmp/{image}"
    mdconfig_results = SSH_TEST(cmd, user, password, ip)
    assert mdconfig_results['result'] is True, mdconfig_results['output']
    if scale is True:
        IMAGES[image] = f"{loops[image]}p1"
    else:
        IMAGES[image] = f"/dev/{mdconfig_results['output'].strip()}s1"


def test_03_import_msdosfs(request):
    depends(request, ["pool_04"], scope="session")
    payload = {
        "device": IMAGES['msdosfs'],
        "fs_type": "msdosfs",
        "fs_options": {},
        "dst_path": dataset_path,
    }
    results = POST("/pool/import_disk/", payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    expect_state(job_id, "SUCCESS")


def test_04_look_if_Directory_slash_File(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    cmd = f'test -f {dataset_path}/Directory/File'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


def test_05_import_nonascii_msdosfs_fails(request):
    depends(request, ["pool_04"], scope="session")
    payload = {
        "device": IMAGES['msdosfs-nonascii'],
        "fs_type": "msdosfs",
        "fs_options": {},
        "dst_path": dataset_path,
    }
    results = POST("/pool/import_disk/", payload)
    assert results.status_code == 200, results.text

    job_id = results.json()

    job = expect_state(job_id, "FAILED")

    assert job["error"] == "rsync failed with exit code 23", job


def test_06_look_if_Directory_slash_File(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    cmd = f'test -f {dataset_path}/Directory/File'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


def test_07_import_nonascii_msdosfs(request):
    depends(request, ["pool_04"], scope="session")
    if scale is True:
        locale = 'utf8'
    else:
        locale = 'ru_RU.UTF-8'
    payload = {
        "device": IMAGES['msdosfs-nonascii'],
        "fs_type": "msdosfs",
        "fs_options": {"locale": locale},
        "dst_path": dataset_path,
    }
    results = POST("/pool/import_disk/", payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    expect_state(job_id, "SUCCESS")


def test_08_look_if_Каталог_slash_Файл(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    cmd = f'test -f {dataset_path}/Каталог/Файл'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


def test_09_import_ntfs(request):
    depends(request, ["pool_04"], scope="session")
    payload = {
        "device": IMAGES['ntfs'],
        "fs_type": "ntfs",
        "fs_options": {},
        "dst_path": dataset_path,
    }
    results = POST("/pool/import_disk/", payload)
    assert results.status_code == 200, results.text

    job_id = results.json()

    expect_state(job_id, "SUCCESS")


def test_10_look_if_Каталог_slash_Файл(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    cmd = f'test -f {dataset_path}/Каталог/Файл'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


@pytest.mark.parametrize('image', ["msdosfs", "msdosfs-nonascii", "ntfs"])
def test_11_stop_image_with_mdconfig(request, image):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    if scale is True:
        cmd = f"losetup -d {loops[image]}"
    else:
        cmd = f"mdconfig -d -u {IMAGES[image].replace('s1', '')}"
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']

    cmd = f"rm -fv /tmp/{image}.gz"
    gunzip_results = SSH_TEST(cmd, user, password, ip)
    assert gunzip_results['result'] is True, gunzip_results['output']

    cmd = f"rm -rfv /tmp/{image}"
    rm_results = SSH_TEST(cmd, user, password, ip)
    assert rm_results['result'] is True, rm_results['output']


def test_12_delete_dataset(request):
    depends(request, ["pool_04"], scope="session")
    results = DELETE(f"/pool/dataset/id/{dataset_url}/")
    assert results.status_code == 200, results.text
