import shlex

import pytest

from middlewared.test.integration.assets.account import user
from middlewared.test.integration.utils import call, ssh

# See middlewared.plugins.smb_.util_passdb: PASSDB_DIR = /var/run/samba-cache/private
PASSDB_PATH = "/var/run/samba-cache/private/passdb.tdb"
USERNAME = "covpdbreinit"


def _delete_passdb_user_key(username):
    """Drop the ``USER_<name>`` entry from passdb.tdb, leaving its ``RID_<rid>``
    entry behind.

    On the next read the dangling RID entry makes ``query_passdb_entries`` raise
    ``PassdbMustReinit``, which is exactly what drives ``passdb_list`` through its
    resync path. Keys are stored as null-terminated C strings, hence ``bytes([0])``.
    """
    py = (
        "import tdb, os; "
        f't = tdb.Tdb("{PASSDB_PATH}", 0, tdb.DEFAULT, os.O_RDWR); '
        f't.delete(b"USER_{username}" + bytes([0])); '
        "t.close()"
    )
    ssh(f"python3 -c {shlex.quote(py)}")


def test_passdb_list_recovers_from_reinit():
    call("smb.synchronize_passdb", job=True)

    with user(
        {
            "username": USERNAME,
            "full_name": "cov passdb reinit",
            "group_create": True,
            "smb": True,
            "password": "PassdbPass1!",
        }
    ):
        assert any(e["username"] == USERNAME for e in call("smb.passdb_list"))

        # Corrupt the passdb so the next read is forced down the reinit path.
        _delete_passdb_user_key(USERNAME)

        entries = call("smb.passdb_list")
        assert any(e["username"] == USERNAME for e in entries)
