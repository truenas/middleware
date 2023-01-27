#!/usr/bin/env python3

# Author: Eric Turgeon
# License: BSD

import pytest
import sys
import os
from time import sleep
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET, is_agent_setup, if_key_listed, SSH_TEST, make_ws_request
from auto_config import sshKey, user, password, ha

from middlewared.test.integration.utils import call


if "controller1_ip" in os.environ:
    ip = os.environ["controller1_ip"]
else:
    from auto_config import ip


def test_000_is_system_ready():
    # other parts of the CI/CD pipeline should have waited
    # for middlewared to report as system.ready so this is
    # a smoke test to see if that's true. If it's not, then
    # the end-user can know that the entire integration run
    # will be non-deterministic because middleware plugins
    # internally expect that the system is ready before
    # propertly responding to REST/WS requests.
    results = GET("/system/ready/", controller_a=ha)
    if not results.json():
        assert False, f'System is not ready. Currently: {GET("/system/state").text}'


def test_00_firstboot_checks():
    expected_datasets = [
        'boot-pool/.system',
        'boot-pool/.system/cores',
        'boot-pool/.system/ctdb_shared_vol',
        'boot-pool/.system/samba4',
        'boot-pool/.system/webui',
        'boot-pool/.system/glusterd',
        'boot-pool/grub'
    ]

    # first make sure our expected datasets actually exist
    payload = {'msg': 'method', 'method': 'zfs.dataset.query', 'params': [
        [], {'select': ['name']}
    ]}
    req = make_ws_request(ip, payload)
    error = req.get('error')
    assert error is None, str(error)
    datasets = [x['name'] for x in req.get('result')]
    for ds in expected_datasets:
        assert ds in datasets, str(datasets)

    # now verify that they are mounted with the expected options
    payload = {'msg': 'method', 'method': 'filesystem.mount_info', 'params': [
        [['fs_type', '=', 'zfs']]
    ]}
    req = make_ws_request(ip, payload)
    error = req.get('error')
    assert error is None, str(error)
    mounts = {x['mount_source']: x for x in req['result']}
    for ds in expected_datasets:
        assert ds in mounts, str(mounts)
        assert mounts[ds]['super_opts'] == ['RW', 'XATTR', 'NOACL', 'CASESENSITIVE'], str(mounts[ds])

    # now verify we don't have any unexpected services running
    payload = {'msg': 'method', 'method': 'service.query', 'params': []}
    req = make_ws_request(ip, payload)
    error = req.get('error')
    assert error is None, str(error)
    services = req['result']

    for srv in services:
        if srv['service'] == 'smartd':
            assert srv['enable'] is True, str(srv)
            # SMART is started with "-q never" which means it should
            # always start in all circumstances
            # (even if there is an invalid (or empty) config)
            assert srv['state'] == 'RUNNING', str(srv)
        else:
            assert srv['enable'] is False, str(srv)
            assert srv['state'] == 'STOPPED', str(srv)


@pytest.mark.parametrize("path,stat", [
    ("/home/admin", {"mode": 0o40700, "uid": 950, "gid": 950}),
    ("/root", {"mode": 0o40700, "uid": 0, "gid": 0}),
])
def test_00_firstboot_checks__stat(path, stat):
    assert stat.items() <= call("filesystem.stat", path).items()


def test_01_Configuring_ssh_settings_for_root_login():
    payload = {"rootlogin": True}
    results = PUT("/ssh/", payload, controller_a=ha)
    assert results.status_code == 200, results.text


def test_02_Enabling_ssh_service_at_boot():
    payload = {'enable': True}
    results = PUT("/service/id/ssh/", payload, controller_a=ha)
    assert results.status_code == 200, results.text


def test_03_Checking_ssh_enable_at_boot():
    results = GET("/service?service=ssh", controller_a=ha)
    assert results.json()[0]['enable'] is True


def test_04_Start_ssh_service():
    payload = {"service": "ssh"}
    results = POST("/service/start/", payload, controller_a=ha)
    assert results.status_code == 200, results.text
    sleep(1)


def test_05_Checking_if_ssh_is_running():
    results = GET("/service?service=ssh", controller_a=ha)
    assert results.json()[0]['state'] == "RUNNING"


@pytest.mark.dependency(name="ssh_password")
def test_06_test_ssh():
    cmd = 'ls -la'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


def test_07_Ensure_ssh_agent_is_setup(request):
    depends(request, ["ssh_password"])
    assert is_agent_setup() is True


def test_10_Ensure_ssh_agent_is_setup(request):
    depends(request, ["ssh_password"])
    assert is_agent_setup() is True


def test_11_Ensure_ssh_key_is_up(request):
    depends(request, ["ssh_password"])
    assert if_key_listed() is True


@pytest.mark.dependency(name="set_ssh_key")
def test_12_Add_ssh_ky_to_root(request):
    depends(request, ["ssh_password"])
    payload = {"sshpubkey": sshKey}
    results = PUT("/user/id/1/", payload, controller_a=ha)
    assert results.status_code == 200, results.text


@pytest.mark.dependency(name="ssh_key")
def test_13_test_ssh_key(request):
    depends(request, ["set_ssh_key"])
    cmd = 'ls -la'
    results = SSH_TEST(cmd, user, None, ip)
    assert results['result'] is True, results['output']
