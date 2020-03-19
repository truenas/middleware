#!/usr/bin/env python3

import pytest
import sys
import os
import time
import re
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST, GET, DELETE, SSH_TEST, send_file
from auto_config import ip, user, password, pool_name, ha, scale

dataset = f"{pool_name}/test_pool"
dataset_url = dataset.replace('/', '%2F')
dataset_path = os.path.join("/mnt", dataset)

IMAGES = {}
loops = {
    'msdosfs': '/dev/loop8',
    'msdosfs-nonascii': '/dev/loop9',
    'ntfs': '/dev/loop10'
}
Reason = 'Skip for HA'
skip_for_ha = pytest.mark.skipif(ha, reason=Reason)
nas_disk = GET('/boot/get_disks/').json()
disk_list = list(POST('/device/get_info/', 'DISK').json().keys())
disk_pool = sorted(list(set(disk_list) - set(nas_disk)))


@pytest.fixture(scope='module')
def pool_data():
    return {}


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


def test_01_get_pool():
    results = GET("/pool/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text


@skip_for_ha
def test_02_creating_a_pool():
    global payload
    payload = {
        "name": pool_name,
        "encryption": False,
        "topology": {
            "data": [
                {"type": "STRIPE", "disks": disk_pool}
            ],
        }
    }
    results = POST("/pool/", payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    expect_state(job_id, "SUCCESS")


def test_03_get_pool_id(pool_data):
    results = GET(f"/pool?name={pool_name}")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    pool_data['id'] = results.json()[0]['id']


def test_04_get_pool_id_info(pool_data):
    results = GET(f"/pool/id/{pool_data['id']}/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    global pool_info
    pool_info = results


@skip_for_ha
@pytest.mark.parametrize('pool_keys', ["name", "topology:data:disks"])
def test_05_looking_pool_info_of_(pool_keys):
    results = pool_info
    if ':' in pool_keys:
        keys_list = pool_keys.split(':')
        if 'disks' in keys_list:
            info = results.json()[keys_list[0]][keys_list[1]]
            disk_list = payload[keys_list[0]][keys_list[1]][0][keys_list[2]]
            for props in info:
                if scale is True:
                    device = re.sub(r'[0-9]+', '', props['device'])
                else:
                    device = props['device'].partition('p')[0]
                assert device in disk_list, results.text
                assert props['disk'] in disk_list, results.text
        else:
            info = results.json()[keys_list[0]][keys_list[1]][keys_list[2]]
    else:
        assert payload[pool_keys] == results.json()[pool_keys], results.text


def test_06_create_dataset():
    result = POST("/pool/dataset/", {"name": dataset})
    assert result.status_code == 200, result.text


@pytest.mark.parametrize('image', ["msdosfs", "msdosfs-nonascii", "ntfs"])
def test_07_setup_function(image):
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


def test_08_import_msdosfs():
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


def test_09_look_if_Directory_slash_File():
    cmd = f'test -f {dataset_path}/Directory/File'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


def test_10_import_nonascii_msdosfs_fails():
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


def test_11_look_if_Directory_slash_File():
    cmd = f'test -f {dataset_path}/Directory/File'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


def test_12_import_nonascii_msdosfs():
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


def test_13_look_if_Каталог_slash_Файл():
    cmd = f'test -f {dataset_path}/Каталог/Файл'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


def test_14_import_ntfs():
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


def test_15_look_if_Каталог_slash_Файл():
    cmd = f'test -f {dataset_path}/Каталог/Файл'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


@pytest.mark.parametrize('image', ["msdosfs", "msdosfs-nonascii", "ntfs"])
def test_16_stop_image_with_mdconfig(image):
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


def test_17_delete_dataset():
    results = DELETE(f"/pool/dataset/id/{dataset_url}/")
    assert results.status_code == 200, results.text
