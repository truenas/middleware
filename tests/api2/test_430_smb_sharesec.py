
import pytest
import sys
import os
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET, DELETE, SSH_TEST
from auto_config import pool_name, user, password, ip, dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skipping for test development testing')

share_name = "my_sharesec"
dataset = f"{pool_name}/smb-sharesec"
dataset_url = dataset.replace('/', '%2F')
share_path = "/mnt/" + dataset

Guests = {
    "domain": "BUILTIN",
    "name": "Guests",
    "sidtype": "ALIAS"
}
Admins = {
    "domain": "BUILTIN",
    "name": "Administrators",
    "sidtype": "ALIAS"
}
Users = {
    "domain": "BUILTIN",
    "name": "Users",
    "sidtype": "ALIAS"
}


def test_01_get_smb_sharesec():
    results = GET('/smb/sharesec/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text


def test_02_creating_smb_sharesec_dataset(request):
    depends(request, ["pool_04"], scope="session")
    payload = {
        "name": dataset,
        "share_type": "SMB"
    }
    results = POST("/pool/dataset/", payload)
    assert results.status_code == 200, results.text


def test_03_creating_a_smb_share_path(request):
    depends(request, ["pool_04"], scope="session")
    global payload, results, smb_id
    payload = {
        "comment": "My Test SMB Share",
        "path": share_path,
        "name": share_name,
    }
    results = POST("/sharing/smb/", payload)
    assert results.status_code == 200, results.text
    smb_id = results.json()['id']


def test_04_starting_cifs_service(request):
    depends(request, ["pool_04"], scope="session")
    payload = {"service": "cifs"}
    results = POST("/service/start/", payload)
    assert results.status_code == 200, results.text


def test_05_get_sharesec_id_with_share_name(request):
    depends(request, ["pool_04"], scope="session")
    global sharesec_id
    results = GET(f'/smb/sharesec/?share_name={share_name}')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    assert isinstance(results.json()[0], dict), results.text
    sharesec_id = results.json()[0]['id']


def test_06_set_smb_sharesec_to_users(request):
    depends(request, ["pool_04"], scope="session")
    global payload
    payload = {
        'share_name': share_name,
        'share_acl': [
            {
                'ae_who_sid': 'S-1-5-32-545',
                'ae_perm': 'FULL',
                'ae_type': 'ALLOWED'
            }
        ]
    }
    results = POST("/smb/sharesec/", payload)
    assert results.status_code == 200, results.text


def test_07_get_smb_sharesec_by_id(request):
    depends(request, ["pool_04"], scope="session")
    global results
    results = GET(f"/smb/sharesec/id/{sharesec_id}")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


@pytest.mark.parametrize('ae', ['ae_who_sid', 'ae_perm', 'ae_type'])
def test_08_verify_share_acl_output_from_smb_sharesec_(request, ae):
    depends(request, ["pool_04"], scope="session")
    ae_result = results.json()['share_acl'][0][ae]
    assert ae_result == payload['share_acl'][0][ae], results.text


@pytest.mark.parametrize('who', ['domain', 'name', 'sidtype'])
def test_09_verify_ae_who_name_output_from_put_smb_sharesec_(request, who):
    depends(request, ["pool_04"], scope="session")
    ae_result = results.json()['share_acl'][0]['ae_who_name'][who]
    assert ae_result == Users[who], results.text


def test_10_change_smb_sharesec_to_admin(request):
    depends(request, ["pool_04"], scope="session")
    global payload, results
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
    assert isinstance(results.json(), dict), results.text


@pytest.mark.parametrize('ae', ['ae_who_sid', 'ae_perm', 'ae_type'])
def test_11_verify_share_acl_output_from_put_smb_sharesec_(request, ae):
    depends(request, ["pool_04"], scope="session")
    ae_result = results.json()['share_acl'][0][ae]
    assert ae_result == payload['share_acl'][0][ae], results.text


@pytest.mark.parametrize('who', ['domain', 'name', 'sidtype'])
def test_12_verify_admin_ae_who_name_output_from_put_smb_sharesec_(request, who):
    depends(request, ["pool_04"], scope="session")
    ae_result = results.json()['share_acl'][0]['ae_who_name'][who]
    assert ae_result == Admins[who], results.text


def test_13_get_smb_sharesec_by_id(request):
    depends(request, ["pool_04"], scope="session")
    global results
    results = GET(f"/smb/sharesec/id/{sharesec_id}")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


@pytest.mark.parametrize('ae', ['ae_who_sid', 'ae_perm', 'ae_type'])
def test_14_verify_share_acl_output_from_get_smb_sharesec_(request, ae):
    depends(request, ["pool_04"], scope="session")
    ae_result = results.json()['share_acl'][0][ae]
    assert ae_result == payload['share_acl'][0][ae], results.text


@pytest.mark.parametrize('who', ['domain', 'name', 'sidtype'])
def test_15_verify_admin_ae_who_name_output_from_get_smb_sharesec_(request, who):
    depends(request, ["pool_04"], scope="session")
    ae_result = results.json()['share_acl'][0]['ae_who_name'][who]
    assert ae_result == Admins[who], results.text


def test_16_change_smb_sharesec_to_guests(request):
    depends(request, ["pool_04"], scope="session")
    global payload, results
    payload = {
        'share_acl': [
            {
                'ae_who_sid': 'S-1-5-32-546',
                'ae_perm': 'FULL',
                'ae_type': 'ALLOWED'
            }
        ]
    }
    results = PUT(f"/smb/sharesec/id/{sharesec_id}/", payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


@pytest.mark.parametrize('ae', ['ae_who_sid', 'ae_perm', 'ae_type'])
def test_17_verify_share_acl_output_from_put_smb_sharesec_(request, ae):
    depends(request, ["pool_04"], scope="session")
    ae_result = results.json()['share_acl'][0][ae]
    assert ae_result == payload['share_acl'][0][ae], results.text


@pytest.mark.parametrize('who', ['domain', 'name', 'sidtype'])
def test_18_verify_guest_ae_who_name_output_from_put_smb_sharesec_(request, who):
    depends(request, ["pool_04"], scope="session")
    ae_result = results.json()['share_acl'][0]['ae_who_name'][who]
    assert ae_result == Guests[who], results.text


def test_19_get_smb_sharesec_by_id(request):
    depends(request, ["pool_04"], scope="session")
    global results
    results = GET(f"/smb/sharesec/id/{sharesec_id}")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


@pytest.mark.parametrize('ae', ['ae_who_sid', 'ae_perm', 'ae_type'])
def test_20_verify_share_acl_output_from_get_smb_sharesec_(request, ae):
    depends(request, ["pool_04"], scope="session")
    ae_result = results.json()['share_acl'][0][ae]
    assert ae_result == payload['share_acl'][0][ae], results.text


@pytest.mark.parametrize('who', ['domain', 'name', 'sidtype'])
def test_21_verify_guest_ae_who_name_output_from_get_smb_sharesec_(request, who):
    depends(request, ["pool_04"], scope="session")
    ae_result = results.json()['share_acl'][0]['ae_who_name'][who]
    assert ae_result == Guests[who], results.text


def test_22_get_smb_sharesec_getacl(request):
    depends(request, ["pool_04"], scope="session")
    payload = {
        "share_name": share_name,
        "options": {
            "resolve_sids": True
        }
    }
    results = POST("/smb/sharesec/getacl/", payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


def test_23_get_smb_sharesec_by_id(request):
    depends(request, ["pool_04"], scope="session")
    results = GET("/smb/sharesec/synchronize_acls/")
    assert results.status_code == 200, results.text


def test_24_delete_share_info_tdb(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    cmd = 'rm /var/db/system/samba4/share_info.tdb'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


def test_25_verify_share_info_tdb_is_deleted(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    cmd = 'test -f /var/db/system/samba4/share_info.tdb'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, results['output']


def test_26_verify_smb_sharesec_is_restored(request):
    depends(request, ["pool_04"], scope="session")
    results = GET(f"/smb/sharesec/id/{sharesec_id}")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    ae_result = results.json()['share_acl'][0]['ae_who_sid']
    assert ae_result != 'S-1-5-32-546', results.text


def test_27_restore_sharesec_with_flush_share_info(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    cmd = 'midclt call smb.sharesec._flush_share_info'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


def test_28_verify_smb_sharesec_is_restored(request):
    depends(request, ["pool_04"], scope="session")
    results = GET(f"/smb/sharesec/id/{sharesec_id}")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    ae_result = results.json()['share_acl'][0]['ae_who_sid']
    assert ae_result == 'S-1-5-32-546', results.text


def test_29_verify_share_info_tdb_is_created(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    cmd = 'test -f /var/db/system/samba4/share_info.tdb'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


def test_30_rename_smb_share_and_verify_share_info_moved(request):
    results = PUT(f"/sharing/smb/id/{smb_id}/",
                  {"name": "my_sharesec2"})
    assert results.status_code == 200, results.text

    results = GET(f"/smb/sharesec/id/{sharesec_id}")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    ae_result = results.json()['share_acl'][0]['ae_who_sid']
    assert ae_result == 'S-1-5-32-546', results.text


def test_31_toggle_share_and_verify_acl_preserved(request):
    results = PUT(f"/sharing/smb/id/{smb_id}/",
                  {"enabled": False})
    assert results.status_code == 200, results.text

    results = PUT(f"/sharing/smb/id/{smb_id}/",
                  {"enabled": True})
    assert results.status_code == 200, results.text

    results = GET(f"/smb/sharesec/id/{sharesec_id}")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    ae_result = results.json()['share_acl'][0]['ae_who_sid']
    assert ae_result == 'S-1-5-32-546', results.text


def test_32_delete_share_acl(request):
    depends(request, ["pool_04"], scope="session")
    results = DELETE(f"/smb/sharesec/id/{sharesec_id}")
    assert results.status_code == 200, results.text


def test_33_starting_cifs_service(request):
    depends(request, ["pool_04"], scope="session")
    payload = {"service": "cifs"}
    results = POST("/service/stop/", payload)
    assert results.status_code == 200, results.text


def test_34_delete_cifs_share(request):
    depends(request, ["pool_04"], scope="session")
    results = DELETE(f"/sharing/smb/id/{smb_id}")
    assert results.status_code == 200, results.text


def test_35_destroying_smb_sharesec_dataset(request):
    depends(request, ["pool_04"], scope="session")
    results = DELETE(f"/pool/dataset/id/{dataset_url}/")
    assert results.status_code == 200, results.text
