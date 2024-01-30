#!/usr/bin/env python3

# License: BSD

import os
import pytest
import random
import string
import sys
from time import sleep
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from auto_config import ip, pool_name, hostname
from functions import PUT, POST, GET, SSH_TEST, DELETE

try:
    Reason = 'BSD host configuration is missing in ixautomation.conf'
    from config import BSD_HOST, BSD_USERNAME, BSD_PASSWORD
    bsd_host_cfg = pytest.mark.skipif(False, reason=Reason)
except ImportError:
    bsd_host_cfg = pytest.mark.skipif(True, reason=Reason)

digit = ''.join(random.choices(string.digits, k=2))

file_mountpoint = f'/tmp/iscsi-file-{hostname}'
zvol_mountpoint = f'/tmp/iscsi-zvol-{hostname}'
target_name = f"target{digit}"
basename = "iqn.2005-10.org.freenas.ctl"
zvol_name = f"ds{digit}"
zvol = f'{pool_name}/{zvol_name}'
zvol_url = zvol.replace('/', '%2F')
pytestmark = pytest.mark.iscsi


def waiting_for_iscsi_to_disconnect(base_target, wait):
    timeout = 0
    while timeout < wait:
        cmd = 'iscsictl -L'
        results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
        if base_target not in results['output']:
            return True
        timeout += 1
        sleep(1)
    else:
        return False


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
def test_02_Add_iSCSI_portal(request):
    depends(request, ["iscsi_01"])
    global portal_id
    payload = {
        'listen': [
            {
                'ip': '0.0.0.0',
            }
        ]
    }
    results = POST("/iscsi/portal/", payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    portal_id = results.json()['id']


@pytest.mark.dependency(name="iscsi_03")
def test_03_Add_iSCSI_target(request):
    depends(request, ["iscsi_02"])
    global target_id
    payload = {
        'name': target_name,
        'groups': [
            {'portal': portal_id}
        ]
    }
    results = POST("/iscsi/target/", payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    target_id = results.json()['id']


@pytest.mark.dependency(name="iscsi_04")
def test_04_Add_a_iSCSI_file_extent(request):
    depends(request, ["iscsi_03"], scope="session")
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


@pytest.mark.dependency(name="iscsi_05")
def test_05_Associate_iSCSI_target(request):
    depends(request, ["iscsi_04"], scope="session")
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


@pytest.mark.dependency(name="iscsi_06")
def test_06_Enable_iSCSI_service(request):
    depends(request, ["iscsi_05"])
    payload = {"enable": True}
    results = PUT("/service/id/iscsitarget/", payload)
    assert results.status_code == 200, results.text


@pytest.mark.dependency(name="iscsi_07")
def test_07_start_iSCSI_service(request):
    depends(request, ["iscsi_05"])
    result = POST(
        '/service/start', {
            'service': 'iscsitarget',
        }
    )
    assert result.status_code == 200, result.text
    sleep(1)


def test_08_Verify_the_iSCSI_service_is_enabled(request):
    depends(request, ["iscsi_05"])
    results = GET("/service/?service=iscsitarget")
    assert results.status_code == 200, results.text
    assert results.json()[0]["state"] == "RUNNING", results.text


@bsd_host_cfg
@pytest.mark.dependency(name="iscsi_09")
def test_09_Connecting_to_iSCSI_target(request):
    depends(request, ["iscsi_05"], scope='session')
    cmd = f'iscsictl -A -p {ip}:3260 -t {basename}:{target_name}'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, f"{results['output']}, {results['stderr']}"


@bsd_host_cfg
@pytest.mark.timeout(20)
@pytest.mark.dependency(name="iscsi_10")
def test_10_Waiting_for_iscsi_connection_before_grabbing_device_name(request):
    depends(request, ["iscsi_09"], scope='session')
    global file_device_name
    file_device_name = ""
    while True:
        cmd = f'iscsictl -L | grep "{basename}:{target_name}"'
        results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
        assert results['result'] is True, f"{results['output']}, {results['stderr']}"
        iscsictl_list = results['stdout'].strip().split()
        if iscsictl_list[2] == "Connected:":
            file_device_name = iscsictl_list[3]
            assert True
            break
        sleep(1)
    while True:
        cmd = f'test -e /dev/{file_device_name}'
        results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
        if results['result']:
            assert True
            break


@bsd_host_cfg
def test_11_Format_the_target_volume(request):
    depends(request, ["iscsi_10"], scope='session')
    cmd = f'umount "/media/{file_device_name}"'
    SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    cmd2 = f'newfs "/dev/{file_device_name}"'
    results = SSH_TEST(cmd2, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, f"{results['output']}, {results['stderr']}"


@bsd_host_cfg
def test_12_Creating_iSCSI_mountpoint(request):
    depends(request, ["iscsi_10"], scope='session')
    cmd = f'mkdir -p {file_mountpoint}'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, f"{results['output']}, {results['stderr']}"


@bsd_host_cfg
@pytest.mark.timeout(10)
def test_13_Mount_the_target_volume(request):
    depends(request, ["iscsi_10"], scope='session')
    cmd = f'mount "/dev/{file_device_name}" "{file_mountpoint}"'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, f"{results['output']}, {results['stderr']}"


@bsd_host_cfg
def test_14_Creating_file(request):
    depends(request, ["iscsi_10"], scope='session')
    cmd = 'touch "%s/testfile"' % file_mountpoint
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, f"{results['output']}, {results['stderr']}"


@bsd_host_cfg
def test_15_Moving_file(request):
    depends(request, ["iscsi_10"], scope='session')
    cmd = 'mv "%s/testfile" "%s/testfile2"' % (file_mountpoint, file_mountpoint)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, f"{results['output']}, {results['stderr']}"


@bsd_host_cfg
def test_16_Copying_file(request):
    depends(request, ["iscsi_10"], scope='session')
    cmd = 'cp "%s/testfile2" "%s/testfile"' % (file_mountpoint, file_mountpoint)
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, f"{results['output']}, {results['stderr']}"


@bsd_host_cfg
def test_17_Deleting_file(request):
    depends(request, ["iscsi_10"], scope='session')
    results = SSH_TEST('rm "%s/testfile2"' % file_mountpoint,
                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, f"{results['output']}, {results['stderr']}"


@bsd_host_cfg
def test_19_Unmounting_iSCSI_volume(request):
    depends(request, ["iscsi_10"], scope='session')
    cmd = f'umount "{file_mountpoint}"'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, f"{results['output']}, {results['stderr']}"
    sleep(1)


@bsd_host_cfg
def test_20_Removing_iSCSI_volume_mountpoint(request):
    depends(request, ["iscsi_10"], scope='session')
    cmd = f'rm -rf "{file_mountpoint}"'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, f"{results['output']}, {results['stderr']}"


@bsd_host_cfg
def test_21_Disconnect_iSCSI_target(request):
    depends(request, ["iscsi_09"], scope='session')
    cmd = f'iscsictl -R -t {basename}:{target_name}'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'] is True, f"{results['output']}, {results['stderr']}"
    # Currently FreeBSD (13.1-RELEASE-p5) does *not* issue a LOGOUT (verified by
    # network capture), so give the target time to react. SCST will log an error, e.g.
    # iscsi-scst: ***ERROR***: Connection 00000000e749085f with initiator iqn.1994-09.org.freebsd:freebsd13.local unexpectedly closed!
    assert waiting_for_iscsi_to_disconnect(f'{basename}:{target_name}', 30)


def test_25_Delete_associate_iSCSI_file_targetextent(request):
    depends(request, ["iscsi_05"], scope="session")
    results = DELETE(f"/iscsi/targetextent/id/{associate_id}/", False)
    assert results.status_code == 200, results.text
    assert results.json(), results.text


def test_26_Delete_iSCSI_file_target(request):
    depends(request, ["iscsi_03"])
    results = DELETE(f"/iscsi/target/id/{target_id}/", False)
    assert results.status_code == 200, results.text
    assert results.json(), results.text


def test_27_Delete_iSCSI_file_extent(request):
    depends(request, ["iscsi_04"])
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
        'name': 'zvol_extent',
        # 'filesize': 536870912,
        # 'path': zvol
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
    cmd = f'iscsictl -A -p {ip}:3260 -t {basename}:{zvol_name}'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'], f"{results['output']}, {results['stderr']}"


@bsd_host_cfg
@pytest.mark.timeout(20)
@pytest.mark.dependency(name="iscsi_35")
def test_35_waiting_for_iscsi_connection_before_grabbing_device_name(request):
    depends(request, ["iscsi_34"])
    global zvol_device_name
    zvol_device_name = ""
    while True:
        cmd = f'iscsictl -L | grep {basename}:{zvol_name}'
        results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
        if results['result'] and "Connected:" in results['output']:
            zvol_device_name = results['stdout'].strip().split()[3]
            assert True
            break
        sleep(1)
    while True:
        cmd = f'test -e /dev/{zvol_device_name}'
        results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
        if results['result']:
            assert True
            break


@bsd_host_cfg
def test_36_format_the_target_volume(request):
    depends(request, ["iscsi_35"])
    cmd = f'umount "/media/{file_device_name}"'
    SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    cmd = f'newfs "/dev/{zvol_device_name}"'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'], f"{results['output']}, {results['stderr']}"


@bsd_host_cfg
@pytest.mark.dependency(name="iscsi_37")
def test_37_creating_iscsi_mountpoint(request):
    depends(request, ["iscsi_35"])
    cmd = f'mkdir -p {zvol_mountpoint}'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'], f"{results['output']}, {results['stderr']}"


@bsd_host_cfg
@pytest.mark.timeout(10)
@pytest.mark.dependency(name="iscsi_38")
def test_38_mount_the_zvol_target_volume(request):
    depends(request, ["iscsi_37"])
    cmd = f'mount /dev/{zvol_device_name} {zvol_mountpoint}'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'], f"{results['output']}, {results['stderr']}"


@bsd_host_cfg
def test_39_creating_file_in_zvol_iscsi_share(request):
    depends(request, ["iscsi_38"])
    cmd = f'touch "{zvol_mountpoint}/myfile.txt"'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'], f"{results['output']}, {results['stderr']}"


@bsd_host_cfg
def test_40_moving_file_in_zvol_iscsi_share(request):
    depends(request, ["iscsi_38"])
    cmd = f'mv "{zvol_mountpoint}/myfile.txt" "{zvol_mountpoint}/newfile.txt"'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'], f"{results['output']}, {results['stderr']}"


@bsd_host_cfg
def test_41_creating_a_directory_in_zvol_iscsi_share(request):
    depends(request, ["iscsi_38"])
    cmd = f'mkdir "{zvol_mountpoint}/mydir"'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'], f"{results['output']}, {results['stderr']}"


@bsd_host_cfg
def test_42_copying_file_to_new_dir_in_zvol_iscsi_share(request):
    depends(request, ["iscsi_38"])
    cmd = f'cp "{zvol_mountpoint}/newfile.txt" "{zvol_mountpoint}/mydir/myfile.txt"'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'], f"{results['output']}, {results['stderr']}"


@bsd_host_cfg
def test_44_unmounting_the_zvol_iscsi_volume(request):
    depends(request, ["iscsi_38"])
    cmd = f'umount "{zvol_mountpoint}"'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'], f"{results['output']}, {results['stderr']}"


@bsd_host_cfg
def test_45_verify_the_zvol_mountpoint_is_empty(request):
    depends(request, ["iscsi_38"])
    cmd = f'test -f {zvol_mountpoint}/newfile.txt'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert not results['result'], f"{results['output']}, {results['stderr']}"


@bsd_host_cfg
def test_46_disconnect_iscsi_zvol_target(request):
    depends(request, ["iscsi_34"])
    cmd = f'iscsictl -R -t {basename}:{zvol_name}'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'], f"{results['output']}, {results['stderr']}"
    assert waiting_for_iscsi_to_disconnect(f'{basename}:{zvol_name}', 30)


@bsd_host_cfg
@pytest.mark.dependency(name="iscsi_47")
def test_47_connecting_to_the_zvol_iscsi_target(request):
    depends(request, ["iscsi_32"])
    cmd = f'iscsictl -A -p {ip}:3260 -t {basename}:{zvol_name}'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'], f"{results['output']}, {results['stderr']}"


@bsd_host_cfg
@pytest.mark.timeout(20)
@pytest.mark.dependency(name="iscsi_48")
def test_48_waiting_for_iscsi_connection_before_grabbing_device_name(request):
    depends(request, ["iscsi_34"])
    global zvol_device_name
    zvol_device_name = ""
    while True:
        cmd = f'iscsictl -L | grep {basename}:{zvol_name}'
        results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
        if results['result'] and "Connected:" in results['output']:
            zvol_device_name = results['stdout'].strip().split()[3]
            assert True
            break
        sleep(1)
    while True:
        cmd = f'test -e /dev/{zvol_device_name}'
        results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
        if results['result']:
            assert True
            break


@bsd_host_cfg
@pytest.mark.timeout(15)
@pytest.mark.dependency(name="iscsi_50")
def test_50_remount_the_zvol_target_volume(request):
    depends(request, ["iscsi_48"])
    cmd = f'umount "/media/{file_device_name}"'
    SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    cmd = f'mount /dev/{zvol_device_name} {zvol_mountpoint}'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'], f"{results['output']}, {results['stderr']}"


@bsd_host_cfg
def test_51_verify_files_and_directory_was_kept_on_the_zvol_iscsi_share(request):
    depends(request, ["iscsi_50"])
    cmd1 = f'test -f {zvol_mountpoint}/newfile.txt'
    results1 = SSH_TEST(cmd1, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results1['result'], results1['output']
    cmd2 = f'test -f "{zvol_mountpoint}/mydir/myfile.txt"'
    results2 = SSH_TEST(cmd2, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results2['result'], results2['output']


@bsd_host_cfg
def test_52_unmounting_the_zvol_iscsi_volume(request):
    depends(request, ["iscsi_50"])
    cmd = f'umount "{zvol_mountpoint}"'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'], f"{results['output']}, {results['stderr']}"
    sleep(1)


@bsd_host_cfg
def test_53_removing_iscsi_volume_mountpoint(request):
    depends(request, ["iscsi_50"])
    cmd = f'rm -rf "{zvol_mountpoint}"'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'], f"{results['output']}, {results['stderr']}"


@bsd_host_cfg
def test_54_redisconnect_iscsi_zvol_target(request):
    depends(request, ["iscsi_47"])
    cmd = f'iscsictl -R -t {basename}:{zvol_name}'
    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
    assert results['result'], f"{results['output']}, {results['stderr']}"
    assert waiting_for_iscsi_to_disconnect(f'{basename}:{zvol_name}', 30)


def test_55_disable_iscsi_service(request):
    depends(request, ["iscsi_06"])
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
    results = DELETE(f"/iscsi/targetextent/id/{zvol_associate_id}/", True)
    assert results.status_code == 200, results.text
    assert results.json(), results.text


def test_59_delete_iscsi_zvol_target(request):
    depends(request, ["iscsi_29"])
    results = DELETE(f"/iscsi/target/id/{zvol_target_id}/", True)
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
