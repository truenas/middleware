#!/usr/bin/env python3

# License: BSD

import pytest
import sys
import os
from pytest_dependency import depends
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import ip, user, password, pool_name, hostname
from functions import PUT, POST, GET, SSH_TEST, DELETE, cmd_test

try:
    Reason = 'BSD host configuration is missing in ixautomation.conf'
    from config import BSD_HOST, BSD_USERNAME, BSD_PASSWORD
    bsd_host_cfg = pytest.mark.skipif(False, reason=Reason)
except ImportError:
    bsd_host_cfg = pytest.mark.skipif(True, reason=Reason)

MOUNTPOINT = f'/tmp/iscsi-{hostname}'
global DEVICE_NAME
DEVICE_NAME = ""
TARGET_NAME = "iqn.1994-09.freenasqa:target0"

zvol_name = "ds1"
zvol = f'{pool_name}/{zvol_name}'
zvol_url = zvol.replace('/', '%2F')
zvol_mountpoint = f'/tmp/iscsi-zvol-{hostname}'
basename = "iqn.2005-10.org.freenas.ctl"


@pytest.mark.dependency(name="iscsi_01")
def test_01_Add_iSCSI_initiator():
    global initiator_id
    payload = {
        'comment': 'Default initiator',
    }
    results = POST("/iscsi/initiator/", payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    initiator_id = results.json()['id']


@pytest.mark.dependency(name="iscsi_02")
def test_02_Add_ISCSI_portal():
    global portal_id
    payload = {
        'listen': [
            {
                'ip': '0.0.0.0',
                'port': 3620
            }
        ]
    }
    results = POST("/iscsi/portal/", payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    portal_id = results.json()['id']


# Add iSCSI target and group
def test_03_Add_ISCSI_target():
    global target_id
    payload = {
        'name': TARGET_NAME,
        'groups': [
            {'portal': portal_id}
        ]
    }
    results = POST("/iscsi/target/", payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    target_id = results.json()['id']


# Add iSCSI extent
def test_04_Add_ISCSI_extent():
    global extent_id
    payload = {
        'type': 'FILE',
        'name': 'extent',
        'filesize': 536870912,
        'path': f'/mnt/{pool_name}/dataset03/iscsi'
    }
    results = POST("/iscsi/extent/", payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    extent_id = results.json()['id']


# Associate iSCSI target
def test_05_Associate_ISCSI_target():
    global associate_id
    payload = {
        'target': target_id,
        'lunid': 1,
        'extent': extent_id
    }
    results = POST("/iscsi/targetextent/", payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    associate_id = results.json()['id']


# Enable the iSCSI service
def test_06_Enable_iSCSI_service():
    payload = {"enable": True}
    results = PUT("/service/id/iscsitarget/", payload)
    assert results.status_code == 200, results.text


def test_07_start_iSCSI_service():
    result = POST(
        '/service/start', {
            'service': 'iscsitarget',
        }
    )
    assert result.status_code == 200, result.text
    sleep(1)


def test_08_Verify_the_iSCSI_service_is_enabled():
    results = GET("/service/?service=iscsitarget")
    assert results.status_code == 200, results.text
    assert results.json()[0]["state"] == "RUNNING", results.text


# when SSH_TEST is functional test using it will need to be added
# Now connect to iSCSI target
@bsd_host_cfg
def test_09_Connecting_to_iSCSI_target():
    cmd = 'iscsictl -A -p %s:3620 -t %s' % (ip, TARGET_NAME)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
@pytest.mark.timeout(10)
def test_10_Waiting_for_iscsi_connection_before_grabbing_device_name():
    while True:
        cmd = f'iscsictl -L | grep {ip}:3620'
        results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
        assert results['result'] is True, results['output']
        iscsictl_list = results['output'].strip().split()
        if iscsictl_list[2] == "Connected:":
            global DEVICE_NAME
            DEVICE_NAME = iscsictl_list[3]
            assert True
            break
        sleep(3)


@bsd_host_cfg
def test_11_Format_the_target_volume():
    cmd = f'umount "/media/{DEVICE_NAME}"'
    SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    cmd2 = f'newfs "/dev/{DEVICE_NAME}"'
    results = SSH_TEST(cmd2, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_12_Creating_iSCSI_mountpoint():
    results = SSH_TEST('mkdir -p "%s"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_13_Mount_the_target_volume():
    cmd = 'mount "/dev/%s" "%s"' % (DEVICE_NAME, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_14_Creating_file():
    cmd = 'touch "%s/testfile"' % MOUNTPOINT
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_15_Moving_file():
    cmd = 'mv "%s/testfile" "%s/testfile2"' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_16_Copying_file():
    cmd = 'cp "%s/testfile2" "%s/testfile"' % (MOUNTPOINT, MOUNTPOINT)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_17_Deleting_file():
    results = SSH_TEST('rm "%s/testfile2"' % MOUNTPOINT,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_18_verifiying_iscsi_session_on_freenas():
    try:
        PUT("/ssh", {
            'rootlogin': True
        })
        PUT("/service/id/ssh", {
            'enable': True
        })
        POST("/service/start", {
            'service': 'ssh',
        })
        results = SSH_TEST('ctladm islist', user, password, ip)
        assert results['result'] is True, results['output']
        hostname = SSH_TEST('hostname', BSD_USERNAME, BSD_PASSWORD, BSD_HOST)['output'].strip()
    except AssertionError as e:
        raise AssertionError(f'Could not verify iscsi session on freenas : {e}')
    else:
        assert hostname in results['output'], 'No active session on FreeNAS for iSCSI'


@bsd_host_cfg
def test_19_Unmounting_iSCSI_volume():
    cmd = f'umount "{MOUNTPOINT}"'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_20_Removing_iSCSI_volume_mountpoint():
    cmd = f'rm -rf "{MOUNTPOINT}"'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


@bsd_host_cfg
def test_21_Disconnect_iSCSI_target():
    cmd = f'iscsictl -R -t {TARGET_NAME}'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, results['output']


# Disable the iSCSI service
def test_22_Disable_iSCSI_service():
    payload = {'enable': False}
    results = PUT("/service/id/iscsitarget/", payload)
    assert results.status_code == 200, results.text


def test_23_stop_iSCSI_service():
    results = POST(
        '/service/stop/', {
            'service': 'iscsitarget',
        }
    )
    assert results.status_code == 200, results.text
    sleep(1)


def test_24_Verify_the_iSCSI_service_is_disabled():
    results = GET("/service/?service=iscsitarget")
    assert results.status_code == 200, results.text
    assert results.json()[0]["state"] == "STOPPED", results.text


# Delete iSCSI target and group
def test_25_Delete_associate_ISCSI_target():
    results = DELETE(f"/iscsi/targetextent/id/{associate_id}/")
    assert results.status_code == 200, results.text
    assert results.json(), results.text


# Delete iSCSI target and group
def test_26_Delete_ISCSI_target():
    results = DELETE(f"/iscsi/target/id/{target_id}/")
    assert results.status_code == 200, results.text
    assert results.json(), results.text


# Remove iSCSI extent
def test_27_Delete_iSCSI_extent():
    results = DELETE(f"/iscsi/extent/id/{extent_id}/")
    assert results.status_code == 200, results.text
    assert results.json(), results.text


@pytest.mark.dependency(name="iscsi_28")
def test_28_creating_zvol_for_the_iscsi_share(request):
    global results, payload
    payload = {
        'name': zvol,
        'type': 'VOLUME',
        'volsize': 655360,
        'volblocksize': '16K'
    }
    results = POST("/pool/dataset/", payload)
    assert results.status_code == 200, results.text


@pytest.mark.dependency(name="iscsi_29")
def test_29_add_iscsi_zvol_target(request):
    depends(request, ["iscsi_28"])
    global zvol_target_id
    payload = {
        'name': zvol_name,
        'groups': [
            {'portal': portal_id}
        ]
    }
    results = POST("/iscsi/target/", payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    zvol_target_id = results.json()['id']


@pytest.mark.dependency(name="iscsi_30")
def test_30_add_iscsi_a_zvol_extent(request):
    depends(request, ["iscsi_28"])
    global zvol_extent_id
    payload = {
        'type': 'DISK',
        'disk': f'zvol/{zvol}',
        'name': 'zvol_extent'
    }
    results = POST("/iscsi/extent/", payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    zvol_extent_id = results.json()['id']


@pytest.mark.dependency(name="iscsi_31")
def test_31_associate_iscsi_zvol_target_and_zvol_extent(request):
    depends(request, ["iscsi_30"])
    global zvol_associate_id
    payload = {
        'target': zvol_target_id,
        'lunid': 1,
        'extent': zvol_extent_id
    }
    results = POST("/iscsi/targetextent/", payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    zvol_associate_id = results.json()['id']


@pytest.mark.dependency(name="iscsi_32")
def test_32_restart_iscsi_service(request):
    depends(request, ["iscsi_31"])
    result = POST('/service/restart', {'service': 'iscsitarget'})
    assert result.status_code == 200, result.text
    sleep(1)


def test_33_verify_the_iscsi_service_is_running(request):
    depends(request, ["iscsi_32"])
    results = GET("/service/?service=iscsitarget")
    assert results.status_code == 200, results.text
    assert results.json()[0]["state"] == "RUNNING", results.text


@bsd_host_cfg
@pytest.mark.dependency(name="iscsi_34")
def test_34_connecting_to_the_zvol_iscsi_target(request):
    depends(request, ["iscsi_32"])
    results = cmd_test(f'iscsictl -A -p {ip}:3620 -t {basename}:{zvol_name}')
    assert results['result'], results['output']


@bsd_host_cfg
@pytest.mark.timeout(15)
@pytest.mark.dependency(name="iscsi_35")
def test_35_waiting_for_iscsi_connection_before_grabbing_device_name(request):
    depends(request, ["iscsi_34"])
    global zvol_device_name
    zvol_device_name = ""
    while True:
        results = cmd_test(f'iscsictl -L | grep {basename}:{zvol_name}')
        if results['result'] and "Connected:" in results['output']:
            zvol_device_name = results['output'].strip().split()[3]
            assert True
            break
        sleep(1)
    sleep(5)


@bsd_host_cfg
def test_36_format_the_target_volume(request):
    depends(request, ["iscsi_35"])
    cmd_test(f'umount "/media/{zvol_device_name}"')
    results = cmd_test(f'newfs "/dev/{zvol_device_name}"')
    assert results['result'], results['output']


@bsd_host_cfg
@pytest.mark.dependency(name="iscsi_37")
def test_37_creating_iscsi_mountpoint(request):
    depends(request, ["iscsi_35"])
    results = cmd_test(f'mkdir -p {zvol_mountpoint}')
    assert results['result'], results['output']


@bsd_host_cfg
@pytest.mark.dependency(name="iscsi_38")
def test_38_mount_the_zvol_target_volume(request):
    depends(request, ["iscsi_37"])
    results = cmd_test(f'mount /dev/{zvol_device_name} {zvol_mountpoint}')
    assert results['result'], results['output']


@bsd_host_cfg
def test_39_creating_file_in_zvol_iscsi_share(request):
    depends(request, ["iscsi_38"])
    results = cmd_test(f'touch "{zvol_mountpoint}/myfile.txt"')
    assert results['result'], results['output']


@bsd_host_cfg
def test_40_moving_file_in_zvol_iscsi_share(request):
    depends(request, ["iscsi_38"])
    cmd = f'mv "{zvol_mountpoint}/myfile.txt" "{zvol_mountpoint}/newfile.txt"'
    results = cmd_test(cmd)
    assert results['result'], results['output']


@bsd_host_cfg
def test_41_creating_a_directory_in_zvol_iscsi_share(request):
    depends(request, ["iscsi_38"])
    results = cmd_test(f'mkdir "{zvol_mountpoint}/mydir"')
    assert results['result'], results['output']


@bsd_host_cfg
def test_42_copying_file_to_new_dir_in_zvol_iscsi_share(request):
    depends(request, ["iscsi_38"])
    cmd = f'cp "{zvol_mountpoint}/newfile.txt" "{zvol_mountpoint}/mydir/myfile.txt"'
    results = cmd_test(cmd)
    assert results['result'], results['output']


@bsd_host_cfg
def test_43_verifying_iscsi_session_on_truenas(request):
    depends(request, ["iscsi_38"])
    try:
        results = SSH_TEST('ctladm islist', user, password, ip)
        assert results['result'], results['output']
        hostname = cmd_test('hostname')['output'].strip()
    except AssertionError as e:
        raise AssertionError(f'Could not verify iscsi session on TrueNAS : {e}')
    else:
        assert hostname in results['output'], 'No active session on TrueNAS for iSCSI'


@bsd_host_cfg
def test_44_unmounting_the_zvol_iscsi_volume(request):
    depends(request, ["iscsi_38"])
    results = cmd_test(f'umount "{zvol_mountpoint}"')
    assert results['result'], results['output']


@bsd_host_cfg
def test_45_verify_the_zvol_mountpoint_is_empty(request):
    depends(request, ["iscsi_38"])
    results = cmd_test(f'test -f {zvol_mountpoint}/newfile.txt')
    assert not results['result'], results['output']


@bsd_host_cfg
def test_46_disconnect_iscsi_zvol_target(request):
    depends(request, ["iscsi_34"])
    results = cmd_test(f'iscsictl -R -t {basename}:{zvol_name}')
    assert results['result'], results['output']


@bsd_host_cfg
@pytest.mark.dependency(name="iscsi_47")
def test_47_connecting_to_the_zvol_iscsi_target(request):
    depends(request, ["iscsi_32"])
    results = cmd_test(f'iscsictl -A -p {ip}:3620 -t {basename}:{zvol_name}')
    assert results['result'], results['output']


@bsd_host_cfg
@pytest.mark.timeout(15)
@pytest.mark.dependency(name="iscsi_48")
def test_48_waiting_for_iscsi_connection_before_grabbing_device_name(request):
    depends(request, ["iscsi_34"])
    global zvol_device_name
    zvol_device_name = ""
    while True:
        results = cmd_test(f'iscsictl -L | grep {basename}:{zvol_name}')
        if results['result'] and "Connected:" in results['output']:
            zvol_device_name = results['output'].strip().split()[3]
            assert True
            break
        sleep(1)


@bsd_host_cfg
def test_49_unmount_media(request):
    depends(request, ["iscsi_48"])
    cmd_test(f'umount "/media/{zvol_device_name}"')


@bsd_host_cfg
@pytest.mark.dependency(name="iscsi_50")
def test_50_remount_the_zvol_target_volume(request):
    depends(request, ["iscsi_48"])
    results = cmd_test(f'mount /dev/{zvol_device_name} {zvol_mountpoint}')
    assert results['result'], results['output']


@bsd_host_cfg
def test_51_verify_files_and_directory_was_kept_on_the_zvol_iscsi_share(request):
    depends(request, ["iscsi_50"])
    results1 = cmd_test(f'test -f {zvol_mountpoint}/newfile.txt')
    assert results1['result'], results1['output']
    results2 = cmd_test(f'test -f "{zvol_mountpoint}/mydir/myfile.txt"')
    assert results2['result'], results2['output']


@bsd_host_cfg
def test_52_unmounting_the_zvol_iscsi_volume(request):
    depends(request, ["iscsi_50"])
    results = cmd_test(f'umount "{zvol_mountpoint}"')
    assert results['result'], results['output']


@bsd_host_cfg
def test_53_removing_iscsi_volume_mountpoint(request):
    depends(request, ["iscsi_50"])
    results = cmd_test(f'rm -rf "{zvol_mountpoint}"')
    assert results['result'], results['output']


@bsd_host_cfg
def test_54_redisconnect_iscsi_zvol_target(request):
    depends(request, ["iscsi_47"])
    results = cmd_test(f'iscsictl -R -t {basename}:{zvol_name}')
    assert results['result'], results['output']


def test_55_disable_iscsi_service(request):
    payload = {'enable': False}
    results = PUT("/service/id/iscsitarget/", payload)
    assert results.status_code == 200, results.text


@pytest.mark.dependency(name="iscsi_56")
def test_56_stop_iscsi_service(request):
    depends(request, ["iscsi_32"])
    results = POST('/service/stop/', {'service': 'iscsitarget'})
    assert results.status_code == 200, results.text
    sleep(1)


def test_57_verify_the_iscsi_service_is_disabled(request):
    depends(request, ["iscsi_56"])
    results = GET("/service/?service=iscsitarget")
    assert results.status_code == 200, results.text
    assert results.json()[0]["state"] == "STOPPED", results.text


def test_58_delete_associate_iscsi_zvol_targe_and_zvol_textent(request):
    depends(request, ["iscsi_31"])
    results = DELETE(f"/iscsi/targetextent/id/{zvol_associate_id}/")
    assert results.status_code == 200, results.text
    assert results.json(), results.text


def test_59_delete_iscsi_zvol_target(request):
    depends(request, ["iscsi_29"])
    results = DELETE(f"/iscsi/target/id/{zvol_target_id}/")
    assert results.status_code == 200, results.text
    assert results.json(), results.text


def test_60_delete_iscsi_zvol_extent(request):
    depends(request, ["iscsi_30"])
    results = DELETE(f"/iscsi/extent/id/{zvol_extent_id}/")
    assert results.status_code == 200, results.text
    assert results.json(), results.text


def test_61_delete_portal(request):
    depends(request, ["iscsi_02"])
    results = DELETE(f"/iscsi/portal/id/{portal_id}/")
    assert results.status_code == 200, results.text
    assert results.json(), results.text


def test_62_delete_iscsi_initiator(request):
    depends(request, ["iscsi_01"])
    results = DELETE(f"/iscsi/initiator/id/{initiator_id}/")
    assert results.status_code == 200, results.text
    assert results.json(), results.text


def test_63_delete_the_zvol_device_by_id(request):
    depends(request, ["iscsi_28"])
    results = DELETE(f'/pool/dataset/id/{zvol_url}')
    assert results.status_code == 200, results.text
