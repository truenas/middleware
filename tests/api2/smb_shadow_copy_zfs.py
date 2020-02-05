#!/usr/bin/env python3

import sys
import os
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET, DELETE, SSH_TEST, wait_on_job
from auto_config import ip, pool_name, password, user


dataset = f"{pool_name}/zshare"
dataset_url = dataset.replace('/', '%2F')
smb_name = "zshare"
zshare_path = "/mnt/" + dataset


def test_01_setting_smb():
    toload = "lanman auth = yes\nntlm auth = yes \nraw NTLMv2 auth = yes"
    payload = {
        "smb_options": toload,
        "guest": "shareuser"
    }
    results = PUT("/smb/", payload)
    assert results.status_code == 200, results.text


def test_02_creating_zshare_dataset():
    payload = {
        "name": dataset,
        "share_type": "SMB"
    }
    results = POST("/pool/dataset/", payload)
    assert results.status_code == 200, results.text


def test_03_giving_shareuse_permissions_to_zshare_dataset():
    global job_id
    payload = {
        "user": "shareuser",
        "group": "wheel"
    }
    results = POST(f"/pool/dataset/id/{dataset_url}/permission/", payload)
    assert results.status_code == 200, results.text
    job_id = results.json()


def test_04_verify_the_job_id_is_successfull():
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_05_creating_a_smb_share_with_shadowcopy():
    global payload, results, smb_id
    payload = {
        "comment": "My ZShare",
        "path": zshare_path,
        "home": False,
        "name": smb_name,
        "shadowcopy": True,
        "auxsmbconf": "shadow:ignore_empty_snaps=false",
        "enabled": True
    }
    results = POST("/sharing/smb/", payload)
    assert results.status_code == 200, results.text
    smb_id = results.json()['id']


def test_06_starting_cifs_service():
    payload = {"service": "cifs", "service-control": {"onetime": True}}
    results = POST("/service/start/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_07_checking_cifs_service_is_running():
    results = GET("/service?service=cifs")
    assert results.json()[0]["state"] == "RUNNING", results.text


def test_08_verify_smbtorture_run_successfully():
    cmd = f'smbtorture //127.0.0.1/{smb_name} -U shareuser%testingvfs.shadow_copy_zfs'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


def test_09_stoping_clif_service():
    payload = {"service": "cifs", "service-control": {"onetime": True}}
    results = POST("/service/stop/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_10_checking_if_cifs_is_stop():
    results = GET("/service?service=cifs")
    assert results.json()[0]['state'] == "STOPPED", results.text


def test_11_delete_smb_share():
    results = DELETE(f"/sharing/smb/id/{smb_id}")
    assert results.status_code == 200, results.text


def test_12_destroying_zshare_dataset():
    results = DELETE(f"/pool/dataset/id/{dataset_url}/")
    assert results.status_code == 200, results.text
