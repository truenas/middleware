import importlib.util
import os

import pytest

import middlewared

MIGRATION = os.path.join(
    os.path.dirname(middlewared.__file__), "alembic", "versions", "27.0", "2026-11-12_12-00_ntp_nts.py"
)


@pytest.fixture(scope="module")
def migration():
    spec = importlib.util.spec_from_file_location("ntp_nts_migration", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
