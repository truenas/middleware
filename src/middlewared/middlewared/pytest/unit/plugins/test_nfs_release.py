import os
from unittest.mock import patch

from middlewared.plugins.nfs_ import release

LOCK = (
    '- 0x00000001d6e1e86a7caddcdb05000000: { type: lock, superblock: "00:43:2", filename: "/w.dat", '
    'owner: "lock id:\\x00\\x00\\x00J" }'
)
OPEN = (
    '- 0x00000001d6e1e86a7caddcdb03000000: { type: open, access: rw, deny: --, superblock: "00:43:2", '
    'filename: "/w.dat", owner: "open id:\\x00" }'
)
REVOKED = '- 0x00000001d6e1e86a7caddcdb05000000: { type: lock, owner: "lock id:\\x00", admin-revoked }'
CLOSED = '- 0x00000001d6e1e86a7caddcdb05000000: { type: lock, owner: "lock id:\\x00" }'


def test_lock_state_line():
    m = release.NFS4_LOCK_STATE.match(LOCK)
    assert (m["major"], m["minor"]) == ("00", "43")
    assert release.NFS4_LOCK_STATE.match(OPEN) is None
    assert release.NFS4_LOCK_STATE.match(REVOKED)["major"] is None


def client(root, name, address, states):
    os.mkdir(root / name)
    (root / name / "info").write_text(f'clientid: 0x1\naddress: "{address}"\nstatus: confirmed\n')
    (root / name / "states").write_text("".join(f"{line}\n" for line in states))


def test_lock_holders(tmp_path):
    client(tmp_path, "1", "10.0.0.5:812", [OPEN, LOCK])
    client(tmp_path, "2", "10.0.0.6:700", [OPEN, CLOSED])
    os.mkdir(tmp_path / "3")  # a client that went away: no states file
    with patch.object(release, "NFS4_CLIENTS_DIR", str(tmp_path)):
        assert release.nfs4_lock_holders() == {os.makedev(0, 0x43): {"10.0.0.5:812"}}
        client(tmp_path, "4", "10.0.0.7:701", [REVOKED])
        assert release.nfs4_lock_holders() is None


def test_export_cache_mentions(tmp_path):
    os.makedirs(tmp_path / "nfsd.export")
    os.makedirs(tmp_path / "nfsd.fh")
    os.mkdir(tmp_path / "a b")
    (tmp_path / "nfsd.export" / "content").write_text(
        f"#path domain(flags)\n# {tmp_path}/a\\040b\t*()\n/mnt/nowhere\t10.0.0.5()\n"
    )
    (tmp_path / "nfsd.fh" / "content").write_text("#domain fsidtype fsid [path]\n* 6 0x0000\n")
    with patch.object(release, "RPC_CACHE_DIR", str(tmp_path)):
        assert release.export_cache_mentions(set(), {os.stat(tmp_path).st_dev})
        assert release.export_cache_mentions({f"{tmp_path}/a b"}, set())
        assert release.export_cache_mentions({"/mnt"}, set())
        assert not release.export_cache_mentions({"/mnt/no"}, {os.stat(tmp_path).st_dev + 1})


def test_flush_export_caches(tmp_path):
    now = 1_000_000
    for cache in release.EXPORT_CACHES:
        os.makedirs(tmp_path / cache)
    (tmp_path / "nfsd.fh" / "flush").write_text(f"{now - 60}\n")
    (tmp_path / "nfsd.export" / "flush").write_text(f"{now}\n")
    sleeps = []
    with (
        patch.object(release, "RPC_CACHE_DIR", str(tmp_path)),
        patch.object(release.time, "time", lambda: now + 0.5),
        patch.object(release.time, "sleep", sleeps.append),
    ):
        release.flush_export_caches()
        # an old flush is written at once, a recent one once its second has passed
        assert (tmp_path / "nfsd.fh" / "flush").read_text() == "1\n"
        assert (tmp_path / "nfsd.export" / "flush").read_text() == "1\n"
        assert sleeps == [0.0, 1.5]
        # asked again, it flushes again: entries made since the last flush outlive it
        (tmp_path / "nfsd.export" / "flush").write_text(f"{now}\n")
        release.flush_export_caches()
        assert (tmp_path / "nfsd.export" / "flush").read_text() == "1\n"
        assert sleeps == [0.0, 1.5, 0.0, 1.5]
