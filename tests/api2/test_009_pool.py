#!/usr/bin/env python3

import pytest
import sys
import os
import time
import re
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST, GET
from auto_config import pool_name, ha, scale

IMAGES = {}
loops = {
    'msdosfs': '/dev/loop8',
    'msdosfs-nonascii': '/dev/loop9',
    'ntfs': '/dev/loop10'
}
nas_disk = GET('/boot/get_disks/', controller_a=ha).json()
disk_list = list(POST('/device/get_info/', 'DISK', controller_a=ha).json().keys())
disk_pool = sorted(list(set(disk_list) - set(nas_disk)))
ha_disk_pool = disk_pool[:1] if ha else None
tank_disk_pool = disk_pool[1:] if ha else disk_pool


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


@pytest.mark.skipif(not ha, reason="Skip for Core")
def test_02_wipe_all_pool_disk():
    for disk in disk_pool:
        payload = {
            "dev": f"{disk}",
            "mode": "QUICK",
            "synccache": True
        }
        results = POST('/disk/wipe/', payload)
        job_id = results.json()
        expect_state(job_id, "SUCCESS")


@pytest.mark.skipif(not ha, reason="Skip for Core")
def test_03_creating_ha_pool():
    global payload
    payload = {
        "name": "ha",
        "encryption": False,
        "topology": {
            "data": [
                {"type": "STRIPE", "disks": ha_disk_pool}
            ],
        }
    }
    results = POST("/pool/", payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    expect_state(job_id, "SUCCESS")


@pytest.mark.dependency(name="pool_04")
def test_04_creating_a_pool():
    global payload
    payload = {
        "name": pool_name,
        "encryption": False,
        "topology": {
            "data": [
                {"type": "STRIPE", "disks": tank_disk_pool}
            ],
        }
    }
    results = POST("/pool/", payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    expect_state(job_id, "SUCCESS")


def test_05_get_pool_id(request, pool_data):
    depends(request, ["pool_04"])
    results = GET(f"/pool?name={pool_name}")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    pool_data['id'] = results.json()[0]['id']


def test_06_get_pool_id_info(request, pool_data):
    depends(request, ["pool_04"])
    results = GET(f"/pool/id/{pool_data['id']}/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    global pool_info
    pool_info = results


@pytest.mark.parametrize('pool_keys', ["name", "topology:data:disks"])
def test_07_looking_pool_info_of_(request, pool_keys):
    depends(request, ["pool_04"])
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
