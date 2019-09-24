
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET, DELETE, SSH_TEST
from auto_config import ip, pool_name, password, user

share_name = "my_sharesec"
dataset = f"{pool_name}/smb-sharesec"
dataset_url = dataset.replace('/', '%2F')
smb_path = "/mnt/" + dataset


def test_01_creating_smb_dataset():
    payload = {
        "name": dataset,
        "share_type": "SMB"
    }
    results = POST("/pool/dataset/", payload)
    assert results.status_code == 200, results.text


def test_02_creating_a_smb_share_path():
    global payload, results, smb_id
    payload = {
        "comment": "My Test SMB Share",
        "path": smb_path,
        "name": share_name,
    }
    results = POST("/sharing/smb/", payload)
    assert results.status_code == 200, results.text
    smb_id = results.json()['id']


def test_03_starting_cifs_service():
    payload = {"service": "cifs", "service-control": {"onetime": True}}
    results = POST("/service/start/", payload)
    assert results.status_code == 200, results.text


def test_04_get_sharesec_by_share_name():
    global sharesec_id
    results = GET(f'/smb/sharesec/?share_name={share_name}')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    assert isinstance(results.json()[0], dict), results.text
    sharesec_id = results.json()[0]['id']


def test_05_set_smb_sharesec_setacl():
    payload = {
        'share_name': share_name,
        'share_acl': [
            {
                'ae_who_sid': 'S-1-5-32-544',
                'ae_perm': 'FULL',
                'ae_type': 'ALLOWED'
            }
        ]
    }
    results = POST(f"/smb/sharesec/", payload)
    assert results.status_code == 200, results.text
    print(results.json())


def test_06_set_smb_sharesec_update():
    payload = {
        'share_acl': [
            {
                'ae_who_sid': 'S-1-5-32-544',
                'ae_perm': 'FULL',
                'ae_type': 'ALLOWED'
            }
        ]
    }
    results = PUT(f"/smb/sharesec/id/{sharesec_id}/", payload)
    assert results.status_code == 200, results.text
    print(results.json())


def test_07_delete_share_acl():
    results = DELETE(f"/smb/sharesec/id/{sharesec_id}")
    assert results.status_code == 200, results.text


def test_08_starting_cifs_service():
    payload = {"service": "cifs", "service-control": {"onetime": True}}
    results = POST("/service/stop/", payload)
    assert results.status_code == 200, results.text


def test_09_delete_cifs_share():
    results = DELETE(f"/sharing/smb/id/{smb_id}")
    assert results.status_code == 200, results.text


def test_10_destroying_smb_dataset():
    results = DELETE(f"/pool/dataset/id/{dataset_url}/")
    assert results.status_code == 200, results.text
