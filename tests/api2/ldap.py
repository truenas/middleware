#!/usr/bin/env python3

import pytest
import sys
import os
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import (
    GET,
    PUT,
    POST,
    DELETE,
    cmd_test
)
from auto_config import pool_name, ip, hostname

Reason = 'LDAPBASEDN, LDAPBASEDN, LDAPBINDDN, LDAPBINDPASSWORD,' \
    ' LDAPHOSTNAME are missing'
try:
    from config import (
        LDAPBASEDN,
        LDAPBINDDN,
        LDAPBINDPASSWORD,
        LDAPHOSTNAME,
        LDAPUSER,
        LDAPPASSWORD
    )
    ldap_test_cfg = pytest.mark.skipif(False, reason=Reason)
except ImportError:
    ldap_test_cfg = pytest.mark.skipif(True, reason=Reason)


MOUNTPOINT = f"/tmp/ldap-{hostname}"
dataset = f"{pool_name}/ldap-test"
dataset_url = dataset.replace('/', '%2F')
SMB_NAME = "TestLDAPShare"
SMB_PATH = f"/mnt/{dataset}"
VOL_GROUP = "wheel"


def test_01_get_ldap():
    results = GET("/ldap/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


def test_02_verify_default_ldap_state_is_disabled():
    results = GET("/ldap/get_state/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), str), results.text
    assert results.json() == "DISABLED", results.text


def test_03_verify_ldap_enable_is_false():
    results = GET("/ldap/")
    assert results.json()["enable"] is False, results.text


def test_04_get_ldap_idmap_backend_choices():
    idmap_backend = {"LDAP", "RFC2307"}
    results = GET("/ldap/idmap_backend_choices/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    assert idmap_backend.issubset(set(results.json())), results.text


def test_05_get_ldap_schema_choices():
    idmap_backend = {"RFC2307", "RFC2307BIS"}
    results = GET("/ldap/schema_choices/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    assert idmap_backend.issubset(set(results.json())), results.text


def test_06_get_ldap_ssl_choices():
    idmap_backend = {"OFF", "ON", "START_TLS"}
    results = GET("/ldap/ssl_choices/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    assert idmap_backend.issubset(set(results.json())), results.text


@ldap_test_cfg
def test_07_setup_and_enabling_ldap():
    payload = {
        "basedn": LDAPBASEDN,
        "binddn": LDAPBINDDN,
        "bindpw": LDAPBINDPASSWORD,
        "hostname": [
            LDAPHOSTNAME
        ],
        "has_samba_schema": True,
        "enable": True
    }
    results = PUT("/ldap/", payload)
    assert results.status_code == 200, results.text


@ldap_test_cfg
def test_08_verify_ldap_state_after_is_enabled_after_enabling_ldap():
    results = GET("/ldap/get_state/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), str), results.text
    assert results.json() == "HEALTHY", results.text


@ldap_test_cfg
def test_09_verify_ldap_enable_is_true():
    results = GET("/ldap/")
    assert results.json()["enable"] is True, results.text


def test_20_creating_ldap_dataset_for_smb():
    results = POST("/pool/dataset/", {"name": dataset})
    assert results.status_code == 200, results.text


def test_11_changing_ldap_dataset_permission():
    global job_id_09
    results = POST(f'/pool/dataset/id/{dataset_url}/permission/', {
        'acl': [],
        'mode': '777',
        'user': 'root',
        'group': 'wheel'
    })
    assert results.status_code == 200, results.text
    job_id_09 = results.json()


def test_12_setting_up_smb_1_for_freebsd():
    global payload, results
    payload = {
        "description": "Test FreeNAS Server",
        "guest": "nobody",
        "enable_smb1": True
    }
    results = PUT("/smb/", payload)
    assert results.status_code == 200, results.text


def test_13_creating_a_smb_share_on_smb_path():
    global smb_id
    payload = {
        "comment": "My Test SMB Share",
        "path": SMB_PATH,
        "name": SMB_NAME,
        "guestok": True,
        "vfsobjects": ["streams_xattr"]
    }
    results = POST("/sharing/smb/", payload)
    assert results.status_code == 200, results.text
    smb_id = results.json()['id']


def test_14_enable_cifs_service():
    results = PUT("/service/id/cifs/", {"enable": True})
    assert results.status_code == 200, results.text


def test_15_verify_if_clif_service_is_enabled():
    results = GET("/service?service=cifs")
    assert results.json()[0]["enable"] is True, results.text


def test_16_starting_cifs_service():
    payload = {"service": "cifs", "service-control": {"onetime": True}}
    results = POST("/service/restart/", payload)
    assert results.status_code == 200, results.text


def test_17_verify_if_cifs_service_is_running():
    results = GET("/service?service=cifs")
    assert results.json()[0]["state"] == "RUNNING", results.text


@ldap_test_cfg
def test_18_creating_ldap_mountpoint():
    results = cmd_test(f'mkdir -p "{MOUNTPOINT}" && sync')
    assert results['result'] is True, results['output']


@ldap_test_cfg
def test_19_store_ldap_credentials_for_mount_smbfs():
    cmd = f'echo "[{ip}:{LDAPUSER.upper()}]" > ~/.nsmbrc && '
    cmd += f'echo "password={LDAPPASSWORD}" >> ~/.nsmbrc'
    results = cmd_test(cmd)
    assert results['result'] is True, results['output']


@ldap_test_cfg
def test_20_mount_smb_share_with_mount_smbfs_and_ldap_credentials():
    cmd = f'mount_smbfs -N -I {ip} -W LDAP -U {LDAPUSER} ' \
        f'//{LDAPUSER}@{ip}/{SMB_NAME} {MOUNTPOINT}'
    results = cmd_test(cmd)
    assert results['result'] is True, results['output']


@ldap_test_cfg
def test_19_umount_ldap_smb_share():
    results = cmd_test(f'umount -f {MOUNTPOINT}')
    assert results['result'] is True, results['output']


@ldap_test_cfg
def test_20_verify_ldap_smb_share_was_unmounted():
    results = cmd_test(f'mount | grep -qv {MOUNTPOINT}')
    assert results['result'] is True, results['output']


def test_21_disable_smb_1():
    global payload, results
    payload = {
        "enable_smb1": False
    }
    results = PUT("/smb/", payload)
    assert results.status_code == 200, results.text


def test_22_stopping_cifs_service():
    payload = {"service": "cifs", "service-control": {"onetime": True}}
    results = POST("/service/stop/", payload)
    assert results.status_code == 200, results.text


def test_23_verify_if_cifs_service_stopped():
    results = GET("/service?service=cifs")
    assert results.json()[0]["state"] == "STOPPED", results.text


def test_24_delete_the_smb_share_for_ldap_testing():
    results = DELETE(f"/sharing/smb/id/{smb_id}")
    assert results.status_code == 200, results.text


@ldap_test_cfg
def test_25_disabling_ldap():
    payload = {
        "enable": False
    }
    results = PUT("/ldap/", payload)
    assert results.status_code == 200, results.text


@ldap_test_cfg
def test_26_verify_ldap_state_after_is_enabled_after_disabling_ldap():
    results = GET("/ldap/get_state/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), str), results.text
    assert results.json() == "DISABLED", results.text


@ldap_test_cfg
def test_27_verify_ldap_enable_is_false():
    results = GET("/ldap/")
    assert results.json()["enable"] is False, results.text


def test_28_destroying_ad_dataset_for_smb():
    results = DELETE(f"/pool/dataset/id/{dataset_url}/")
    assert results.status_code == 200, results.text
