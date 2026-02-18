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


def test_count_method_calls():
    """
    Make a bunch of API calls using SSH, websocket, and webshell connections
    to verify that usage.gather counts them all in its method_stats dictionary.

    Call usage.gather once at the beginning and once at the end.
    """
    baseline_stats = call('usage.gather')['method_stats']

    # SSH
    ssh('midclt call system.info')

    # Websocket client
    with client(ssl=False) as c:
        c.call('system.version')

    # Webshell
    output = webshell_exec('midclt call system.ready')
    assert 'true' in output.lower() or 'false' in output.lower()

    # Multiple calls in the same SSH session
    ssh('midclt call system.host_id;' * 3)
    ssh('midclt call system.product_type; midclt call system.version; midclt call failover.licensed')

    # Reopen websocket connection
    with client(ssl=False) as c:
        c.call('system.product_type')

    # Check the reported number of calls against the
    # expected number for each method that was called
    COUNTS = {
        'system.info': 1,
        'system.version': 2,
        'system.ready': 1,
        'system.host_id': 3,
        'system.product_type': 2,
        'failover.licensed': 1,
    }
    latest_stats = call('usage.gather')['method_stats']
    inconsistencies = []
    for method, expected_count in COUNTS.items():
        actual_count = latest_stats.get(method, 0) - baseline_stats.get(method, 0)
        if actual_count != expected_count:
            inconsistencies.append((method, expected_count, actual_count))

    assert not inconsistencies, '\n'.join(
        f'{method}: expected {expected_count}, got {actual_count}'
        for method, expected_count, actual_count in inconsistencies
    )
