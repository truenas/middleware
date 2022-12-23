import base64
import os
import re
import subprocess
import tempfile

import pytest

from middlewared.test.integration.utils import call

from auto_config import dev_test
pytestmark = pytest.mark.skipif(dev_test, reason='Skipping for test development testing')


@pytest.fixture()
def snmpd_running():
    call("service.start", "snmp")
    yield


def test_freenas_mib(snmpd_running):
    with tempfile.NamedTemporaryFile(suffix=".txt") as f:
        f.write(base64.b64decode(
            call("filesystem.file_get_contents", "/usr/local/share/snmp/mibs/TRUENAS-MIB.txt").encode("ascii")
        ))
        f.flush()

        snmp = subprocess.run(
            f"snmpwalk -v2c -c public -m {f.name} {os.environ['MIDDLEWARE_TEST_IP']} "
            "1.3.6.1.4.1.50536",
            shell=True,
            capture_output=True,
            text=True,
        )
        assert snmp.returncode == 0, snmp.stderr

    assert "TRUENAS-MIB::zpoolName.1 = STRING: boot-pool\n" in snmp.stdout
    assert re.search(r"^TRUENAS-MIB::zfsArcSize\.0 = Gauge32: ([1-9][0-9]+)\n", snmp.stdout, re.MULTILINE), snmp.stdout
