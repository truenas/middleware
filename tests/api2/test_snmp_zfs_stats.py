import re
import subprocess
import time

import pytest

from middlewared.test.integration.utils import call, host, ssh


REMOTE_MIB_PATH = '/usr/local/share/snmp/mibs/TRUENAS-MIB.txt'

# Expected OIDs and their SNMP types.
# ARC subtree: 1.3.6.1.4.1.50536.1.3
ARC_OIDS = {
    'zfsArcSize': 'Gauge32',
    'zfsArcMeta': 'Gauge32',
    'zfsArcData': 'Gauge32',
    'zfsArcHits': 'Gauge32',
    'zfsArcMisses': 'Gauge32',
    'zfsArcC': 'Gauge32',
    'zfsArcMissPercent': 'STRING',
    'zfsArcCacheHitRatio': 'STRING',
    'zfsArcCacheMissRatio': 'STRING',
}

# L2ARC subtree: 1.3.6.1.4.1.50536.1.4
L2ARC_OIDS = {
    'zfsL2ArcHits': 'Counter32',
    'zfsL2ArcMisses': 'Counter32',
    'zfsL2ArcRead': 'Counter32',
    'zfsL2ArcWrite': 'Counter32',
    'zfsL2ArcSize': 'Gauge32',
}

# ZIL subtree: 1.3.6.1.4.1.50536.1.5
ZIL_OIDS = {
    'zfsZilstatOps1sec': 'Counter64',
    'zfsZilstatOps5sec': 'Counter64',
    'zfsZilstatOps10sec': 'Counter64',
}

# zpool table columns: 1.3.6.1.4.1.50536.1.1
ZPOOL_COLUMNS = {
    'zpoolIndex': 'INTEGER',
    'zpoolName': 'STRING',
    'zpoolHealth': 'STRING',
    'zpoolReadOps': 'Counter64',
    'zpoolWriteOps': 'Counter64',
    'zpoolReadBytes': 'Counter64',
    'zpoolWriteBytes': 'Counter64',
    'zpoolReadOps1sec': 'Counter64',
    'zpoolWriteOps1sec': 'Counter64',
    'zpoolReadBytes1sec': 'Counter64',
    'zpoolWriteBytes1sec': 'Counter64',
}

# zvol table columns: 1.3.6.1.4.1.50536.1.2
ZVOL_COLUMNS = {
    'zvolIndex': 'INTEGER',
    'zvolDescr': 'STRING',
    'zvolUsedBytes': 'Counter64',
    'zvolAvailableBytes': 'Counter64',
    'zvolReferencedBytes': 'Counter64',
}

# ARC OIDs that must be nonzero on any running system
ARC_NONZERO = {'zfsArcSize', 'zfsArcC'}


@pytest.fixture(scope='module')
def snmpd_running():
    call('service.control', 'START', 'snmp', job=True)
    time.sleep(3)
    yield


@pytest.fixture(scope='module')
def local_mib(tmp_path_factory):
    """Fetch the TRUENAS-MIB from the remote host and write it to a local tempfile."""
    content = ssh(f'cat {REMOTE_MIB_PATH}')
    assert content, 'Failed to fetch TRUENAS-MIB from remote host'
    path = tmp_path_factory.mktemp('mibs') / 'TRUENAS-MIB.txt'
    path.write_text(content)
    return str(path)


def snmpwalk_raw(mib_path, oid):
    """Walk an OID subtree from the test runner, return raw stdout."""
    result = subprocess.run(
        f'snmpwalk -v2c -c public -m {mib_path} {host().ip} {oid}',
        shell=True,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def parse_scalars(stdout):
    """Parse snmpwalk output into {name: (type, value)} for scalar OIDs."""
    parsed = {}
    for line in stdout.splitlines():
        # TRUENAS-MIB::zfsArcSize.0 = Gauge32: 12345
        m = re.match(r'TRUENAS-MIB::(\w+)\.\d+\s+=\s+(\w+):\s+(.*)', line)
        if m:
            parsed[m.group(1)] = (m.group(2), m.group(3).strip(' "'))
    return parsed


def parse_table_rows(stdout):
    """Parse snmpwalk table output into {row_index: {column_name: (type, value)}}."""
    rows = {}
    for line in stdout.splitlines():
        # TRUENAS-MIB::zpoolName.1 = STRING: "boot-pool"
        m = re.match(r'TRUENAS-MIB::(\w+)\.(\d+)\s+=\s+(\w+):\s+(.*)', line)
        if m:
            col_name, row_idx, snmp_type, value = m.group(1), m.group(2), m.group(3), m.group(4)
            rows.setdefault(row_idx, {})[col_name] = (snmp_type, value.strip(' "'))
    return rows


def assert_scalar_shape(stats, expected_oids):
    for name, expected_type in expected_oids.items():
        assert name in stats, f'{name} missing from subtree walk'
        actual_type, _ = stats[name]
        assert actual_type == expected_type, (
            f'{name}: expected type {expected_type}, got {actual_type}'
        )


def assert_table_row_shape(row, expected_columns, row_idx):
    for col_name, expected_type in expected_columns.items():
        assert col_name in row, f'{col_name} missing from table row {row_idx}'
        actual_type, _ = row[col_name]
        assert actual_type == expected_type, (
            f'{col_name} row {row_idx}: expected type {expected_type}, got {actual_type}'
        )


def test_arc_oid_shape(snmpd_running, local_mib):
    """All ARC OIDs are present with correct SNMP types."""
    stats = parse_scalars(snmpwalk_raw(local_mib, '1.3.6.1.4.1.50536.1.3'))
    assert_scalar_shape(stats, ARC_OIDS)

    for name in ARC_NONZERO:
        _, value = stats[name]
        assert int(value) > 0, f'{name} should be nonzero on a running system'


def test_l2arc_oid_shape(snmpd_running, local_mib):
    """All L2ARC OIDs are present with correct SNMP types."""
    stats = parse_scalars(snmpwalk_raw(local_mib, '1.3.6.1.4.1.50536.1.4'))
    assert_scalar_shape(stats, L2ARC_OIDS)


def test_zil_oid_shape(snmpd_running, local_mib):
    """All ZIL OIDs are present with correct SNMP types."""
    stats = parse_scalars(snmpwalk_raw(local_mib, '1.3.6.1.4.1.50536.1.5'))
    assert_scalar_shape(stats, ZIL_OIDS)


def test_zpool_table_shape(snmpd_running, local_mib):
    """zpool table has at least one row (boot-pool) with all expected columns and types."""
    rows = parse_table_rows(snmpwalk_raw(local_mib, '1.3.6.1.4.1.50536.1.1'))
    assert rows, 'zpool table is empty — expected at least boot-pool'

    for row_idx, row in rows.items():
        assert_table_row_shape(row, ZPOOL_COLUMNS, row_idx)

    # boot-pool should always be present
    pool_names = {row['zpoolName'][1] for row in rows.values() if 'zpoolName' in row}
    assert 'boot-pool' in pool_names
