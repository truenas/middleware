import contextlib
from itertools import chain
import time

import pytest

from auto_config import password, pool_name, user
from middlewared.test.integration.assets.ftp import ftp_server
from middlewared.test.integration.assets.nfs import nfs_server
from middlewared.test.integration.assets.pool import dataset as nfs_dataset
from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.utils.client import truenas_server, client
from middlewared.test.integration.utils.shell import webshell_exec
from protocols import SSH_NFS, ftp_connection, nfs_share


class GatherTypes:
    expected = {
        'total_capacity': ['total_capacity'],
        'backup_data': ['data_backup_stats', 'data_without_backup_size'],
        'applications': ['apps', 'catalog_items', 'docker_images'],
        'filesystem_usage': ['datasets', 'zvols'],
        'ha_stats': ['ha_licensed'],
        'directory_service_stats': ['directory_services'],
        'cloud_services': ['cloud_services'],
        'hardware': ['hardware'],
        'network': ['network'],
        'system_version': ['platform', 'version'],
        'system': ['system_hash', 'usage_version', 'system'],
        'pools': ['pools', 'total_raw_capacity'],
        'services': ['services'],
        'nfs': ['NFS'],
        'ftp': ['FTP'],
        'sharing': ['shares'],
        'vms': ['vms'],
        'vendor_info': ['is_vendored', 'vendor_name'],
        'hypervisor': ['hypervisor', 'is_virtualized'],
        'method_stats': ['method_stats']
        # Add new gather type here
    }


@pytest.fixture(scope="module")
def get_usage_sample():
    sample = call('usage.gather')
    yield sample


@contextlib.contextmanager
def count_calls(method: str, num_calls: int = 1):
    baseline_stats = call('usage.gather')['method_stats']
    baseline_count = baseline_stats.get(method, 0)

    yield baseline_count

    updated_stats = call('usage.gather')['method_stats']
    updated_count = updated_stats.get(method, 0)

    measured = updated_count - baseline_count
    assert measured == num_calls, f'Expected {num_calls} call(s) to {method}, got {measured} instead'


def test_gather_types(get_usage_sample):
    """ Confirm we find the expected types. Fail if this test needs updating """
    sample = get_usage_sample
    expected = list(chain.from_iterable(GatherTypes.expected.values()))

    # If there is a mismatch it probably means this test module needs to be updated
    assert set(expected).symmetric_difference(sample) == set(), "Expected empty set. "\
        f"Missing an entry in the output ({len(sample)} entries) or test needs updating ({len(expected)} entries)"


def test_nfs_reporting(get_usage_sample):
    """ Confirm we are correctly reporting the number of NFS connections """
    # NOTE: NFSv3 can be wildly inaccurate.  Connections are recorded by mount requests.
    #       Connections get cleared by umount requests.  Stale entries can easily accumulate.
    #       NFSv4 clients can be slow-ish to showup.
    # Initial state should have NFSv[3,4] and possibly some stale NFSv3 connections from previous tests
    assert set(get_usage_sample['NFS']['enabled_protocols']) == set(["NFSV3", "NFSV4"])

    nfs_path = f'/mnt/{pool_name}/test_nfs'
    with nfs_dataset("test_nfs"):
        with nfs_share(nfs_path):
            with nfs_server():
                # Wait a couple secs for clients to report in
                time.sleep(2)
                baseline_sample = call('usage.gather')['NFS']['num_clients']

                # Establish a new connection.
                with SSH_NFS(truenas_server.ip, nfs_path,
                             user=user, password=password, ip=truenas_server.ip):
                    usage_sample = call('usage.gather')
                    assert usage_sample['NFS']['num_clients'] == baseline_sample + 1


def test_ftp_reporting(get_usage_sample):
    """ Confirm we are correctly reporting the number of connections """
    # Initial state should have no connections
    assert get_usage_sample['FTP']['num_connections'] == 0

    # Establish two connections
    with ftp_server():
        with ftp_connection(truenas_server.ip):
            with ftp_connection(truenas_server.ip):
                usage_sample = call('usage.gather')
                assert usage_sample['FTP']['num_connections'] == 2


# Possible TODO:  Add validation of the entries


def test_method_stats_via_midclt_ssh():
    """
    Verify that midclt calls via SSH are tracked in method_stats.

    midclt calls over SSH are considered external/interactive sessions and should
    be counted in the usage statistics.
    """
    with count_calls('system.info'):
        ssh('midclt call system.info')


def test_method_stats_via_loopback_client():
    """
    Verify that WebSocket client connections via loopback are tracked in method_stats.

    Client connections over TCP/IP (even loopback) are considered external and should
    be counted in the usage statistics.
    """
    with count_calls('system.version'):
        with client(ssl=False) as c:
            c.call('system.version')


def test_method_stats_via_webshell_midclt():
    """
    Verify that midclt calls through webshell are tracked.

    This tests sending commands through the webshell WebSocket terminal interface.
    Commands run through the webshell are considered external/interactive.
    """
    with count_calls('system.ready'):
        # Execute midclt command through the webshell
        output = webshell_exec('midclt call system.ready')
        # Verify the command executed successfully (output should contain "true" or "false")
        assert 'true' in output.lower() or 'false' in output.lower()


def test_method_stats_multiple_calls():
    """
    Verify that method_stats correctly accumulates multiple calls to the same method.
    """
    num_calls = 3
    with count_calls('system.host_id', num_calls):
        for _ in range(num_calls):
            ssh('midclt call system.host_id')


def test_method_stats_different_methods():
    """
    Verify that method_stats tracks different methods independently.
    """
    # Get baseline stats
    baseline_stats = call('usage.gather')['method_stats']

    # Track counts for multiple methods
    methods_to_test = [
        'system.product_type',
        'system.version',
        'failover.licensed',
    ]

    baseline_counts = {
        method: baseline_stats.get(method, 0)
        for method in methods_to_test
    }

    # Make exactly one call to each method via midclt
    for method in methods_to_test:
        ssh(f'midclt call {method}')

    # Get updated stats
    updated_stats = call('usage.gather')['method_stats']

    # Verify each method's count increased by exactly 1 independently
    for method in methods_to_test:
        updated_count = updated_stats.get(method, 0)
        baseline_count = baseline_counts[method]
        assert updated_count == baseline_count + 1


def test_method_stats_mixed_connection_types():
    """
    Verify that method_stats tracks calls from different connection types correctly.

    Tests both SSH (midclt) and WebSocket client connections for the same method.
    """
    with count_calls('system.product_type', 2):
        ssh('midclt call system.product_type')

        # Make 1 call via WebSocket client
        with client(ssl=False) as c:
            c.call('system.product_type')
