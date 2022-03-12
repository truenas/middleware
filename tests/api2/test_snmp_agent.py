import os
import re
import subprocess

import pytest

from middlewared.test.integration.utils import call


@pytest.fixture()
def snmpd_running():
    call("service.start", "snmp")
    yield


def test_freenas_mib(snmpd_running):
    snmp = subprocess.run(
        f"snmpwalk -v2c -c public -m /usr/local/share/snmp/mibs/FREENAS-MIB.txt {os.environ['MIDDLEWARE_TEST_IP']} "
        "1.3.6.1.4.1.50536",
        shell=True,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "FREENAS-MIB::zpoolDescr.1 = STRING: boot-pool\n" in snmp.stdout
    assert "FREENAS-MIB::datasetDescr.1 = STRING: boot-pool/.system\n" in snmp.stdout
    assert re.search(r"^FREENAS-MIB::zfsArcSize\.0 = Gauge32: ([1-9][0-9]+)\n", snmp, re.MULTILINE), snmp.stdout
