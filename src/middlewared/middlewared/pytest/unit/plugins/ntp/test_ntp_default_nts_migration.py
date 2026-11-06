import importlib.util
import os

import pytest

import middlewared

MIGRATION = os.path.join(
    os.path.dirname(middlewared.__file__), "alembic", "versions", "27.0", "2026-10-23_12-00_ntp_nts.py"
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


@pytest.mark.parametrize(
    "address,expected",
    [
        ("0.debian.pool.ntp.org", True),
        ("192.0.2.1", True),
        ("2001:db8::1", True),
        # Stored before the API took only single words; chronyd would read the rest as options or directives
        ("127.0.0.1\npidfile /etc/passwd", False),
        ("127.0.0.1 port 1234", False),
        ("127.0.0.1\t", False),
        ("", False),
        (None, False),
    ],
)
def test_only_single_word_addresses_are_kept(migration, address, expected):
    assert migration.is_single_word(address) is expected
