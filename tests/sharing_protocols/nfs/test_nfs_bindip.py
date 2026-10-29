"""NFS ``bindip`` configuration tests.

``nfs.bindip_choices`` reports only statically configured addresses, so
these tests need an interface with a static IP.  They live here because
the ``sharing_protocols`` session bootstrap configures one
(``set_static_interface`` in ``../conftest.py``).  The ``api2`` suite
runs against a DHCP interface, where the same tests only ever skipped.
"""

import pytest

from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.utils.client import truenas_server

pp = pytest.param

# Stands in for the address of the server under test, which the
# parametrize list cannot know at collection time.
SERVER_IP = "SERVER_IP"


def nfsd_bind_hosts():
    """Addresses in ``host`` of the ``[nfsd]`` section of /etc/nfs.conf.
    Empty when nfsd binds every address."""
    section = None
    for line in ssh("cat /etc/nfs.conf").splitlines():
        if line.startswith("["):
            section = line.strip()[1:-1]
        elif section == "nfsd" and line.startswith("host = "):
            return line.split(" = ", 1)[1].split(",")

    return []


def rpcbind_bind_hosts():
    """Addresses in the ``-h`` options of ``OPTIONS`` in /etc/default/rpcbind.
    Empty when rpcbind binds every address."""
    for line in ssh("cat /etc/default/rpcbind").splitlines():
        if line.startswith("OPTIONS="):
            opts = line.split("=", 1)[1].split()
            assert opts[0] == "-w", f"rpcbind OPTIONS lost the hard-wired -w: {line}"
            return [opts[i + 1] for i, opt in enumerate(opts) if opt == "-h"]

    return []


@pytest.fixture
def restore_bindip():
    original = call("nfs.config")["bindip"]
    try:
        yield
    finally:
        call("nfs.update", {"bindip": original})


def test_config_bindip(start_nfs, restore_bindip):
    """nfs.update writes bindip to the nfsd and the rpcbind config files."""
    assert truenas_server.ip in call("nfs.bindip_choices")

    assert call("nfs.config")["bindip"] == []
    assert nfsd_bind_hosts() == []
    assert rpcbind_bind_hosts() == []

    call("nfs.update", {"bindip": [truenas_server.ip]})

    assert call("nfs.config")["bindip"] == [truenas_server.ip]
    assert nfsd_bind_hosts() == [truenas_server.ip]
    assert rpcbind_bind_hosts() == [truenas_server.ip]


@pytest.mark.parametrize(
    "bindip,errmsg",
    [
        pp(["1.2.3.4"], "Cannot use", id="not in choices"),
        pp(["a.b.c.d"], "not appear to be", id="not a valid IP"),
        pp([SERVER_IP, "8.8.8.8"], "Cannot use", id="2nd entry not in choices"),
        pp([SERVER_IP, "ixsystems.com"], "not appear to be", id="2nd entry not a valid IP"),
        pp([SERVER_IP, None], "Input should be", id="2nd entry is None"),
        pp([SERVER_IP, "a.b.c.d", "ixsystems.com"], "not appear to be", id="two invalid entries"),
    ],
)
def test_config_bindip_rejects_invalid_entry(start_nfs, bindip, errmsg):
    """nfs.update rejects an address that is not a valid IP or that
    nfs.bindip_choices does not report, and keeps the stored config."""
    payload = [truenas_server.ip if entry == SERVER_IP else entry for entry in bindip]

    with pytest.raises((ValueError, ValidationErrors)) as ve:
        call("nfs.update", {"bindip": payload})
    if ve.typename == "ValueError":
        assert errmsg in str(ve.value)
    else:
        assert errmsg in str(ve.value.errors[0])

    assert call("nfs.config")["bindip"] == []
