from base64 import b64encode
from unittest.mock import Mock

import pytest

from middlewared.plugins.smb_ import sharesec
from middlewared.service_exception import MatchNotFound
from middlewared.utils.security_descriptor import sd_bytes_to_share_acl, share_acl_to_sd_bytes
from middlewared.utils.tdb import get_tdb_handle

SAMPLE_DOM_SID = "S-1-5-21-3510196835-1033636670-2319939847-200108"
SAMPLE_BUILTIN_SID = "S-1-5-32-544"
WORLD_SID = "S-1-1-0"
SHARE_NAME = "sharesec_share"


@pytest.fixture
def share_info_tdb(tmp_path, monkeypatch):
    """Redirect share_info.tdb reads and writes into a temporary file."""
    path = str(tmp_path / "share_info.tdb")
    monkeypatch.setattr(sharesec, "LOCAL_SHARE_INFO_FILE", path)
    monkeypatch.setattr(sharesec, "TDB_SHARE_INFO_CONFIG", (path, sharesec.SHARE_INFO_TDB_OPTIONS))
    return path


def share_sec_service(stored_acl):
    """Build a ShareSec service backed by a single share holding `stored_acl` in the config database."""

    def call_sync(method, *args, **kwargs):
        match method:
            case "datastore.config":
                return {"cifs_srv_stateful_failover": False}
            case "datastore.query":
                return [{"name": SHARE_NAME, "home": False, "share_acl": stored_acl}]
            case _:
                raise AssertionError(f"{method}: unexpected middleware call")

    middleware = Mock()
    middleware.call_sync = call_sync
    return sharesec.ShareSec(middleware)


@pytest.mark.parametrize(
    "legacy,expected",
    [
        # Descriptors for a single well-known SID are short enough to contain no base64
        # alphabet characters at all, so an encoding mismatch on them yields an empty
        # value rather than an error.
        (
            f"{WORLD_SID}:ALLOWED/0x0/FULL",
            [{"ae_who_sid": WORLD_SID, "ae_perm": "FULL", "ae_type": "ALLOWED"}],
        ),
        (
            f"{SAMPLE_BUILTIN_SID}:ALLOWED/0x0/FULL",
            [{"ae_who_sid": SAMPLE_BUILTIN_SID, "ae_perm": "FULL", "ae_type": "ALLOWED"}],
        ),
        (
            f"{SAMPLE_DOM_SID}:ALLOWED/0x0/READ",
            [{"ae_who_sid": SAMPLE_DOM_SID, "ae_perm": "READ", "ae_type": "ALLOWED"}],
        ),
        (
            f"{SAMPLE_BUILTIN_SID}:ALLOWED/0x0/FULL {SAMPLE_DOM_SID}:DENIED/0x0/CHANGE",
            [
                {"ae_who_sid": SAMPLE_BUILTIN_SID, "ae_perm": "FULL", "ae_type": "ALLOWED"},
                {"ae_who_sid": SAMPLE_DOM_SID, "ae_perm": "CHANGE", "ae_type": "DENIED"},
            ],
        ),
    ],
)
def test__flush_legacy_share_acl(share_info_tdb, legacy, expected):
    """Test that a legacy share ACL string is flushed as a packed security descriptor."""
    share_sec_service(legacy).flush_share_info()

    stored = sharesec.fetch_share_acl(SHARE_NAME, False)
    assert stored != b""
    assert sd_bytes_to_share_acl(stored) == expected


def test__flush_share_acl(share_info_tdb):
    """Test that a base64-encoded share ACL is decoded before being flushed."""
    sd_bytes = share_acl_to_sd_bytes(
        [
            {"ae_who_sid": SAMPLE_DOM_SID, "ae_perm": "CHANGE", "ae_type": "ALLOWED"},
        ]
    )

    share_sec_service(b64encode(sd_bytes).decode()).flush_share_info()

    assert sharesec.fetch_share_acl(SHARE_NAME, False) == sd_bytes


def test__flush_share_without_acl(share_info_tdb):
    """Test that a share with no stored ACL is skipped so that samba applies its default."""
    share_sec_service("").flush_share_info()

    with pytest.raises(MatchNotFound):
        sharesec.fetch_share_acl(SHARE_NAME, False)


def test__flush_removes_unusable_record(share_info_tdb):
    """Test that a zero-length record is dropped on flush.

    Such a record cannot be unmarshalled, so samba applies its S-1-1-0 FULL default
    while getacl would otherwise report an empty ACL. Removing it makes the two agree.
    """
    with get_tdb_handle(share_info_tdb, sharesec.SHARE_INFO_TDB_OPTIONS) as hdl:
        hdl.store(f"{sharesec.SHARE_INFO_SD_PREFIX}{SHARE_NAME}", b"")

    share_sec_service("").flush_share_info()

    with pytest.raises(MatchNotFound):
        sharesec.fetch_share_acl(SHARE_NAME, False)
