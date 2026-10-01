import importlib.util
import os

import pytest

import middlewared

MIGRATION = os.path.join(
    os.path.dirname(middlewared.__file__), "alembic", "versions", "27.0", "2026-10-01_12-00_ntp_nts.py"
)


@pytest.fixture(scope="module")
def migration():
    spec = importlib.util.spec_from_file_location("ntp_nts_migration", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FREEBSD = [f"{i}.freebsd.pool.ntp.org" for i in range(3)]
DEBIAN = [f"{i}.debian.pool.ntp.org" for i in range(3)]


@pytest.mark.parametrize(
    "addresses,domain_member,expected",
    [
        # A new database, before middleware moves the defaults from FreeBSD's pool to Debian's
        (FREEBSD, False, True),
        (DEBIAN, False, True),
        (list(reversed(DEBIAN)), False, True),
        (DEBIAN, True, False),
        (DEBIAN + ["ntp.example.net"], False, False),
        (DEBIAN + ["time.cloudflare.com", "ntppool1.time.nl"], False, False),
        (DEBIAN[:2], False, False),
        (DEBIAN[:2] + ["ntp.example.net"], False, False),
        (DEBIAN[:2] + DEBIAN[:1], False, False),
        (FREEBSD[:2] + DEBIAN[:1], False, False),
        ([], False, False),
    ],
)
def test_only_the_truenas_default_servers_get_nts_ones(migration, addresses, domain_member, expected):
    assert migration.should_add_default_nts(addresses, domain_member) is expected


def test_nts_servers_come_from_two_operators(migration):
    assert migration.NTS_SERVERS == ("time.cloudflare.com", "ntppool1.time.nl")
