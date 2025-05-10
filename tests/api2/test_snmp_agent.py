import re
import subprocess
import tempfile
import time

import pytest

from middlewared.test.integration.utils import call, host, ssh


@pytest.fixture()
def snmpd_running():
    call("service.control", "START", "snmp", job=True)
    time.sleep(2)
    yield


def test_truenas_mib_elements(snmpd_running):
    mib_file = "/usr/local/share/snmp/mibs/TRUENAS-MIB.txt"
    with tempfile.NamedTemporaryFile(mode='w') as f:
        lines = ssh(f'cat {mib_file}')
        assert lines

        f.writelines(lines)
        f.flush()

        snmp = subprocess.run(
            f"snmpwalk -v2c -c public -m {f.name} {host().ip} "
            "1.3.6.1.4.1.50536",
            shell=True,
            capture_output=True,
            text=True,
        )
        assert snmp.returncode == 0, snmp.stderr
        assert "TRUENAS-MIB::zpoolName.1 = STRING: boot-pool\n" in snmp.stdout
        assert re.search(
            r"^TRUENAS-MIB::zfsArcSize\.0 = Gauge32: ([1-9][0-9]+)\n", snmp.stdout, re.MULTILINE
        ), snmp.stdout
