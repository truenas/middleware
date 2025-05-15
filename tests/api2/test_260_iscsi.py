import random
import string
from time import sleep

import pytest
from assets.websocket.iscsi import initiator, portal, target, target_extent_associate
from auto_config import hostname, pool_name
from functions import SSH_TEST

from middlewared.test.integration.assets.iscsi import iscsi_extent
from middlewared.test.integration.assets.pool import dataset
from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.utils.client import truenas_server

try:
    from config import BSD_HOST, BSD_PASSWORD, BSD_USERNAME
    have_bsd_host_cfg = True
except ImportError:
    have_bsd_host_cfg = False

pytestmark = pytest.mark.skipif(not have_bsd_host_cfg, reason='BSD host configuration is missing in ixautomation.conf')

digit = ''.join(random.choices(string.digits, k=2))

file_mountpoint = f'/tmp/iscsi-file-{hostname}'
zvol_mountpoint = f'/tmp/iscsi-zvol-{hostname}'
target_name = f"target{digit}"
basename = "iqn.2005-10.org.freenas.ctl"
zvol_name = f"ds{digit}"
zvol = f'{pool_name}/{zvol_name}'
zvol_url = zvol.replace('/', '%2F')


def has_session_present(target):
    results = call('iscsi.global.sessions', [['target', '=', target]])
    assert isinstance(results, list), results
    return bool(len(results))


def waiting_for_iscsi_to_disconnect(base_target, wait):
    timeout = 0
    # First check that the client no longer sees the target logged in
    while timeout < wait:
        cmd = 'iscsictl -L'
        results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
        if base_target not in results['output']:
            break
        timeout += 1
        sleep(1)
    # Next check that the SCALE does not see a session to the target
    while timeout < wait:
        if not has_session_present(base_target):
            return True
        timeout += 1
        sleep(1)
    else:
        return False


def wait_for_iscsi_connection_before_grabbing_device_name(iqn, wait=60):
    timeout = 0
    device_name = ""
    while timeout < wait:
        cmd = f'iscsictl -L | grep {iqn}'
        results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
        if results['result'] and "Connected:" in results['output']:
            device_name = results['stdout'].strip().split()[3]
            if device_name.startswith('probe'):
                timeout += 1
                sleep(1)
                continue
            assert True
            break
        timeout += 1
        sleep(1)
    while timeout < wait:
        cmd = f'test -e /dev/{device_name}'
        results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
        if results['result']:
            assert True
            break
        timeout += 1
        sleep(1)
    assert timeout < wait, f"Timed out waiting {wait} seconds for {iqn} to surface"
    return device_name


@pytest.fixture(scope='module')
def fix_initiator():
    with initiator() as config:
        yield config


@pytest.fixture(scope='module')
def fix_portal():
    with portal() as config:
        yield {'portal': config}


@pytest.fixture(scope='module')
def fix_iscsi_enabled():
    payload = {"enable": True}
    config = call('service.update', 'iscsitarget', payload)
    try:
        yield config
    finally:
        payload = {"enable": False}
        config = call('service.update', 'iscsitarget', payload)


@pytest.fixture(scope='module')
def fix_iscsi_started(fix_iscsi_enabled):
    call('service.control', 'START', 'iscsitarget', job=True)
    sleep(1)
    try:
        yield
    finally:
        call('service.control', 'STOP', 'iscsitarget', job=True)


def test_add_iscsi_initiator(fix_initiator):
    result = call('iscsi.initiator.query')
    assert len(result) == 1, result
    assert result[0]['comment'] == 'Default initiator', result


def test_add_iscsi_portal(fix_portal):
    result = call('iscsi.portal.query')
    assert len(result) == 1, result
    assert result[0]['listen'][0]['ip'] == '0.0.0.0', result


def test_enable_iscsi_service(fix_iscsi_enabled):
    pass


def test_start_iscsi_service(fix_iscsi_started):
    result = call('service.query', [['service', '=', 'iscsitarget']], {'get': True})
    assert result["state"] == "RUNNING", result


class FileExtent:

    @pytest.fixture(scope='class')
    def fix_extent(self):
        filepath = f'/mnt/{pool_name}/iscsi_file_extent'
        data = {
            'type': 'FILE',
            'name': 'extent',
            'filesize': 536870912,
            'path': filepath
        }
        try:
            with iscsi_extent(data) as config:
                yield config
        finally:
            ssh(f'rm -f {filepath}')


class ZvolExtent:

    @pytest.fixture(scope='class')
    def fix_extent(self):
        zvol_data = {
            'type': 'VOLUME',
            'volsize': 655360,
            'volblocksize': '16K'
        }
        with dataset(zvol_name, zvol_data, pool_name):
            extent_data = {
                'type': 'DISK',
                'disk': f'zvol/{zvol}',
                'name': 'zvol_extent',
            }
            with iscsi_extent(extent_data) as config:
                yield config


class Target:

    @pytest.fixture(scope='class')
    def fix_target(self, fix_portal):
        result = {}
        result.update(fix_portal)
        with target(self.TARGET_NAME, [{'portal': fix_portal['portal']['id']}]) as config:
            result.update({'target': config})
            result.update({'iqn': f'{basename}:{self.TARGET_NAME}'})
            yield result

    @pytest.fixture(scope='class')
    def fix_targetextent(self, fix_target, fix_extent):
        result = {}
        result.update(fix_target)
        result.update(fix_extent)
        with target_extent_associate(fix_target['target']['id'], fix_extent['id'], 1) as config:
            result.update({'targetextent': config})
            yield result

    def test_add_iscsi_target(self, fix_target):
        result = call('iscsi.target.query', [['name', '=', fix_target['target']['name']]])
        assert len(result) == 1, result

    def test_add_iscsi_file_extent(self, fix_extent):
        result = call('iscsi.extent.query')
        assert len(result) == 1, result

    def test_associate_iscsi_target(self, fix_targetextent):
        result = call('iscsi.targetextent.query')
        assert len(result) == 1, result


class LoggedInTarget:

    @pytest.fixture(scope='class')
    def fix_connect_to_target(self, fix_iscsi_started, fix_targetextent):
        iqn = fix_targetextent['iqn']
        cmd = f'iscsictl -A -p {truenas_server.ip}:3260 -t {iqn}'
        results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
        assert results['result'] is True, f"{results['output']}, {results['stderr']}"
        try:
            yield fix_targetextent
        finally:
            cmd = f'iscsictl -R -t {iqn}'
            results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
            assert results['result'] is True, f"{results['output']}, {results['stderr']}"
            # Currently FreeBSD (13.1-RELEASE-p5) does *not* issue a LOGOUT (verified by
            # network capture), so give the target time to react. SCST will log an error, e.g.
            # iscsi-scst: ***ERROR***: Connection 00000000e749085f with initiator iqn.1994-09.org.freebsd:freebsd13.local unexpectedly closed!
            assert waiting_for_iscsi_to_disconnect(f'{iqn}', 30)

    @pytest.fixture(scope='class')
    def fix_target_surfaced(self, fix_connect_to_target):
        result = {}
        result.update(fix_connect_to_target)
        iqn = fix_connect_to_target['iqn']
        device_name = wait_for_iscsi_connection_before_grabbing_device_name(iqn)
        assert device_name != ""
        result.update({'device': device_name})
        yield result

    def test_connect_to_iscsi_target(self, fix_connect_to_target):
        pass

    def test_target_surfaced(self, fix_target_surfaced):
        pass


class Formatted:
    @pytest.fixture(scope='class')
    def fix_format_target_volume(self, fix_target_surfaced):
        device_name = fix_target_surfaced['device']
        cmd = f'umount "/media/{device_name}"'
        SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
        cmd2 = f'newfs "/dev/{device_name}"'
        results = SSH_TEST(cmd2, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
        assert results['result'] is True, f"{results['output']}, {results['stderr']}"
        yield fix_target_surfaced

    def test_format_target_volume(self, fix_format_target_volume):
        pass


class Mounted:
    @pytest.fixture(scope='class')
    def fix_create_iscsi_mountpoint(self):
        cmd = f'mkdir -p {self.MOUNTPOINT}'
        results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
        assert results['result'] is True, f"{results['output']}, {results['stderr']}"
        try:
            yield
        finally:
            cmd = f'rm -rf "{self.MOUNTPOINT}"'
            results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
            assert results['result'] is True, f"{results['output']}, {results['stderr']}"

    @pytest.fixture(scope='class')
    def fix_mount_target_volume(self, fix_target_surfaced, fix_create_iscsi_mountpoint):
        device_name = fix_target_surfaced['device']
        cmd = f'mount "/dev/{device_name}" "{self.MOUNTPOINT}"'
        # Allow some settle time (if we've just logged in a previously formatted target)
        sleep(5)
        results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
        assert results['result'] is True, f"{results['output']}, {results['stderr']}"
        try:
            result = {}
            result.update(fix_target_surfaced)
            result.update({'mountpoint': self.MOUNTPOINT})
            yield
        finally:
            cmd = f'umount "{self.MOUNTPOINT}"'
            results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
            assert results['result'] is True, f"{results['output']}, {results['stderr']}"

    def test_create_iscsi_mountpoint(self, fix_create_iscsi_mountpoint):
        pass

    def test_mount_target_volume(self, fix_mount_target_volume):
        pass


class TestFileTarget(FileExtent, Target):
    TARGET_NAME = target_name

    class TestLoggedIn(LoggedInTarget):
        pass

        class TestFormatted(Formatted):
            pass

            class TestMounted(Mounted):
                MOUNTPOINT = file_mountpoint

                def test_create_file(self, fix_mount_target_volume):
                    cmd = 'touch "%s/testfile"' % self.MOUNTPOINT
                    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
                    assert results['result'] is True, f"{results['output']}, {results['stderr']}"

                def test_move_file(self, fix_mount_target_volume):
                    cmd = 'mv "%s/testfile" "%s/testfile2"' % (self.MOUNTPOINT, self.MOUNTPOINT)
                    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
                    assert results['result'] is True, f"{results['output']}, {results['stderr']}"

                def test_copy_file(self, fix_mount_target_volume):
                    cmd = 'cp "%s/testfile2" "%s/testfile"' % (self.MOUNTPOINT, self.MOUNTPOINT)
                    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
                    assert results['result'] is True, f"{results['output']}, {results['stderr']}"

                def test_delete_file(self, fix_mount_target_volume):
                    results = SSH_TEST('rm "%s/testfile2"' % self.MOUNTPOINT,
                                       BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
                    assert results['result'] is True, f"{results['output']}, {results['stderr']}"


class TestZvolTarget(ZvolExtent, Target):
    TARGET_NAME = zvol_name

    class TestLoggedIn(LoggedInTarget):
        pass

        class TestFormatted(Formatted):
            pass

            class TestMounted(Mounted):
                MOUNTPOINT = zvol_mountpoint

                def test_create_file(self, fix_mount_target_volume):
                    cmd = 'touch "%s/myfile.txt"' % self.MOUNTPOINT
                    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
                    assert results['result'] is True, f"{results['output']}, {results['stderr']}"

                def test_move_file(self, fix_mount_target_volume):
                    cmd = 'mv "%s/myfile.txt" "%s/newfile.txt"' % (self.MOUNTPOINT, self.MOUNTPOINT)
                    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
                    assert results['result'] is True, f"{results['output']}, {results['stderr']}"

                def test_create_directory_in_zvol_iscsi_share(self, fix_mount_target_volume):
                    cmd = f'mkdir "{self.MOUNTPOINT}/mydir"'
                    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
                    assert results['result'], f"{results['output']}, {results['stderr']}"

                def test_copy_file_to_new_dir_in_zvol_iscsi_share(self, fix_mount_target_volume):
                    cmd = f'cp "{self.MOUNTPOINT}/newfile.txt" "{self.MOUNTPOINT}/mydir/myfile.txt"'
                    results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
                    assert results['result'], f"{results['output']}, {results['stderr']}"

        def test_verify_the_zvol_mountpoint_is_empty(self):
            cmd = f'test -f {zvol_mountpoint}/newfile.txt'
            results = SSH_TEST(cmd, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
            assert not results['result'], f"{results['output']}, {results['stderr']}"

    class TestLoggedInAgain(LoggedInTarget):
        pass

        class TestMounted(Mounted):
            MOUNTPOINT = zvol_mountpoint

            def test_verify_files_and_directory_kept_on_the_zvol_iscsi_share(self):
                cmd1 = f'test -f {zvol_mountpoint}/newfile.txt'
                results1 = SSH_TEST(cmd1, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
                assert results1['result'], results1['output']
                cmd2 = f'test -f "{zvol_mountpoint}/mydir/myfile.txt"'
                results2 = SSH_TEST(cmd2, BSD_USERNAME, BSD_PASSWORD, BSD_HOST)
                assert results2['result'], results2['output']
