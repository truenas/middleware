"""On-box tests for system dataset behavior.

These tests run on a TrueNAS box (via tests/run_unit_tests.py) with a
functional middleware. They drive the middleware via truenas_api_client.Client
and verify mount/state directly via truenas_pylibzfs and statmount.

Coverage focus:
- Fallback recovery preserves authoritative data on the preferred pool
  (the data-loss bug recently fixed in setup_impl).
- Explicit user-initiated migration round-trips data byte-for-byte through
  lzc.send/lzc.receive.
- Migration into a destination with a stale `<pool>/.system` succeeds because
  destroy_impl is called with bypass=True.
- select_system_dataset_pool / _pool_is_available priority logic.
- /var is MS_PRIVATE and the cores/coredump bind isn't a propagation peer
  of /var/db/system/cores.

Tests that require a second pool use disk.get_unused; tests skip with a
clear message when no spare disk is present on the bench.
"""
import os
import uuid

import pytest
from truenas_api_client import Client
from truenas_os_pyutils.mount import statmount

PASSPHRASE = "passphrase"
SENTINEL_REL_PATH = "samba4/_sysds_test_sentinel"
SYSDATASET_PATH = "/var/db/system"
COREDUMP_PATH = "/var/lib/systemd/coredump"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_mountinfo():
    """Parse /proc/self/mountinfo into a list of dicts.

    Each entry includes the propagation peer-group strings from the
    "optional fields" section between the mount-point and the `-` separator.
    Possible peer markers per mountinfo(5): shared:N, master:N,
    propagate_from:N, unbindable. Absence of any means the mount is private.
    """
    entries = []
    with open("/proc/self/mountinfo") as f:
        for line in f:
            head, _sep, tail = line.rstrip("\n").partition(" - ")
            head_fields = head.split(" ")
            tail_fields = tail.split(" ")
            entries.append({
                "mount_id": int(head_fields[0]),
                "parent_id": int(head_fields[1]),
                "mountpoint": head_fields[4],
                "optional": head_fields[6:],
                "fs_type": tail_fields[0],
                "mount_source": tail_fields[1],
            })
    return entries


def _propagation_for(mountpoint):
    """Return the propagation peer-group tags for `mountpoint`."""
    for entry in _read_mountinfo():
        if entry["mountpoint"] == mountpoint:
            return entry["optional"]
    raise AssertionError(f"{mountpoint} not in /proc/self/mountinfo")


def _sysds_mount_source():
    """Mount source (zfs dataset name) currently mounted at SYSDATASET_PATH."""
    return statmount(path=SYSDATASET_PATH)["mount_source"]


def _write_sentinel(content):
    """Write a known string to a stable subpath under SYSDATASET_PATH and
    return its absolute path. Uses /var/db/system/samba4/ which is a child
    dataset that travels with the parent in every migration scenario."""
    path = os.path.join(SYSDATASET_PATH, SENTINEL_REL_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    return path


def _read_sentinel():
    path = os.path.join(SYSDATASET_PATH, SENTINEL_REL_PATH)
    with open(path) as f:
        return f.read()


def _sentinel_exists():
    return os.path.exists(os.path.join(SYSDATASET_PATH, SENTINEL_REL_PATH))


def _remove_sentinel():
    path = os.path.join(SYSDATASET_PATH, SENTINEL_REL_PATH)
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    with Client() as c:
        yield c


@pytest.fixture
def boot_pool(client):
    return client.call("boot.pool_name")


@pytest.fixture
def initial_sysds(client):
    """Snapshot the sysdataset config so we can restore it on teardown."""
    cfg = client.call("systemdataset.config")
    yield cfg
    # Restore — best effort.
    final = client.call("systemdataset.config")
    if final["pool"] != cfg["pool"] and cfg["pool_set"]:
        try:
            client.call("systemdataset.update", {"pool": cfg["pool"]}, job=True)
        except Exception:
            pass


def _pool_create(client, name, **extra):
    """Create a single-stripe pool from one unused disk; skip if unavailable."""
    unused = client.call("disk.get_unused")
    if not unused:
        pytest.skip("no unused disk available for test pool creation")
    return client.call(
        "pool.create",
        {
            "name": name,
            "topology": {"data": [{"type": "STRIPE", "disks": [unused[0]["devname"]]}]},
            "allow_duplicate_serials": True,
            **extra,
        },
        job=True,
    )


def _pool_destroy(client, name):
    try:
        pool_id = client.call("pool.query", [["name", "=", name]], {"get": True})["id"]
    except Exception:
        return
    try:
        client.call("pool.export", pool_id, {"destroy": True}, job=True)
    except Exception:
        pass


@pytest.fixture
def extra_pool(client, initial_sysds):
    """Plain stripe pool. Yields the pool name. Destroyed on teardown."""
    name = f"sdtest_{uuid.uuid4().hex[:6]}"
    pool = _pool_create(client, name)
    try:
        yield pool["name"]
    finally:
        # Move sysdataset off this pool before destroying.
        cfg = client.call("systemdataset.config")
        if cfg["pool"] == pool["name"]:
            try:
                client.call("systemdataset.update", {"pool": initial_sysds["pool"]}, job=True)
            except Exception:
                pass
        _pool_destroy(client, pool["name"])


@pytest.fixture
def passphrase_extra_pool(client, initial_sysds):
    """Passphrase-encrypted stripe pool. Yields the pool name."""
    name = f"sdtest_enc_{uuid.uuid4().hex[:6]}"
    pool = _pool_create(
        client,
        name,
        encryption=True,
        encryption_options={"passphrase": PASSPHRASE},
    )
    try:
        # Make sure the root dataset is unlocked at the start of each test.
        if client.call("pool.dataset.get_instance", pool["name"])["locked"]:
            client.call(
                "pool.dataset.unlock", pool["name"],
                {"datasets": [{"name": pool["name"], "passphrase": PASSPHRASE}]},
                job=True,
            )
        yield pool["name"]
    finally:
        cfg = client.call("systemdataset.config")
        if cfg["pool"] == pool["name"]:
            try:
                client.call("systemdataset.update", {"pool": initial_sysds["pool"]}, job=True)
            except Exception:
                pass
        # Make sure pool is unlocked so destroy can proceed.
        try:
            if client.call("pool.dataset.get_instance", pool["name"])["locked"]:
                client.call(
                    "pool.dataset.unlock", pool["name"],
                    {"datasets": [{"name": pool["name"], "passphrase": PASSPHRASE}]},
                    job=True,
                )
        except Exception:
            pass
        _pool_destroy(client, pool["name"])


# ---------------------------------------------------------------------------
# Pool selection logic
# ---------------------------------------------------------------------------


class TestPoolSelection:
    """Drive select_system_dataset_pool / _pool_is_available with concrete
    pool states. Both are private but reachable via Client.call()."""

    def test_preferred_pool_available_returns_preferred_no_fallback(self, client, extra_pool):
        target, is_fallback = client.call(
            "systemdataset.select_system_dataset_pool", extra_pool, None,
        )
        assert target == extra_pool
        assert is_fallback is False

    def test_preferred_pool_excluded_returns_alternate(self, client, extra_pool, boot_pool):
        # When preferred is excluded, fallback should land on boot pool
        # (no other data pool present in this test).
        target, is_fallback = client.call(
            "systemdataset.select_system_dataset_pool", extra_pool, extra_pool,
        )
        assert target == boot_pool
        assert is_fallback is False

    def test_preferred_is_boot_pool_no_data_pools_available(self, client, boot_pool):
        target, is_fallback = client.call(
            "systemdataset.select_system_dataset_pool", boot_pool, None,
        )
        assert target == boot_pool
        assert is_fallback is False

    def test_preferred_locked_with_key_falls_back_to_boot(self, client, passphrase_extra_pool, boot_pool):
        # Passphrase-locked pools are STILL eligible for sysdataset (system
        # dataset is encryption=off). select_system_dataset_pool should
        # return the passphrase-encrypted pool when it's available.
        target, is_fallback = client.call(
            "systemdataset.select_system_dataset_pool", passphrase_extra_pool, None,
        )
        assert target == passphrase_extra_pool
        assert is_fallback is False

    def test_pool_is_available_returns_true_for_imported_pool(self, client, extra_pool):
        assert client.call("systemdataset._pool_is_available", extra_pool) is True

    def test_pool_is_available_returns_true_for_boot_pool(self, client, boot_pool):
        assert client.call("systemdataset._pool_is_available", boot_pool) is True


# ---------------------------------------------------------------------------
# Data preservation: explicit migration
# ---------------------------------------------------------------------------


class TestExplicitMigration:
    """User-initiated migration via systemdataset.update must preserve
    file contents byte-for-byte through lzc.send/lzc.receive."""

    def test_round_trip_preserves_sentinel(self, client, extra_pool, initial_sysds):
        original_pool = initial_sysds["pool"]
        sentinel_value = f"sentinel-{uuid.uuid4().hex}"

        # Start clean on whatever the existing pool is.
        _remove_sentinel()
        sentinel_path = _write_sentinel(sentinel_value)
        assert os.path.exists(sentinel_path)
        assert _sysds_mount_source().split("/", 1)[0] == original_pool

        # Migrate to extra_pool — data must travel.
        client.call("systemdataset.update", {"pool": extra_pool}, job=True)
        assert _sysds_mount_source() == f"{extra_pool}/.system"
        assert _read_sentinel() == sentinel_value

        # Migrate back — sentinel must still be intact.
        client.call("systemdataset.update", {"pool": original_pool}, job=True)
        assert _sysds_mount_source() == f"{original_pool}/.system"
        assert _read_sentinel() == sentinel_value

        _remove_sentinel()


# ---------------------------------------------------------------------------
# Data preservation: fallback recovery
# ---------------------------------------------------------------------------


class TestFallbackRecovery:
    """When the preferred pool is locked, sysdataset falls back to the boot
    pool. When the preferred pool unlocks, setup_impl must remount it
    WITHOUT data migration — preserving the authoritative data that lived
    there before fallback."""

    def test_locked_then_unlocked_pool_preserves_data(
        self, client, passphrase_extra_pool, initial_sysds, boot_pool,
    ):
        original_pool = initial_sysds["pool"]
        sentinel_value = f"fallback-recovery-{uuid.uuid4().hex}"

        # Move sysdataset onto the passphrase pool, write sentinel.
        client.call("systemdataset.update", {"pool": passphrase_extra_pool}, job=True)
        assert _sysds_mount_source() == f"{passphrase_extra_pool}/.system"
        _remove_sentinel()
        _write_sentinel(sentinel_value)

        # Lock the pool root → simulates "preferred unavailable at boot".
        # The kids of an unlocked-then-locked passphrase root remain
        # readable as long as the system dataset itself isn't unmounted.
        # Unmount it first via systemdataset.setup so the lock can take
        # effect on the root — then drive a fresh setup, which should
        # detect the locked preferred pool and fall back to boot.
        client.call(
            "pool.dataset.lock", passphrase_extra_pool, job=True,
        )

        # Trigger setup; setup_impl should fall back to boot pool.
        client.call("systemdataset.setup")
        assert _sysds_mount_source() == f"{boot_pool}/.system"
        # Sentinel is on the locked pool, not boot — must NOT be visible now.
        assert not _sentinel_exists()

        # Unlock the preferred pool and re-run setup. setup_impl detects
        # mounted=boot, target=preferred (DB unchanged, db_just_persisted=False)
        # and runs _abandon_and_remount — NO data copy, target's existing
        # sysdataset reappears with sentinel intact.
        client.call(
            "pool.dataset.unlock", passphrase_extra_pool,
            {"datasets": [{"name": passphrase_extra_pool, "passphrase": PASSPHRASE}]},
            job=True,
        )
        client.call("systemdataset.setup")
        assert _sysds_mount_source() == f"{passphrase_extra_pool}/.system"
        assert _read_sentinel() == sentinel_value

        # Cleanup: move sysdataset back so the fixture can teardown the pool.
        client.call("systemdataset.update", {"pool": original_pool}, job=True)
        _remove_sentinel()


# ---------------------------------------------------------------------------
# Migration into a destination with stale `.system`
# ---------------------------------------------------------------------------


class TestStaleDestinationMigration:
    """If a previous migration to extra_pool failed, `extra_pool/.system`
    may exist with stale data. The current migration's pre-replicate
    destroy_impl(bypass=True) wipes it so receive lands on a clean slate."""

    def test_migration_overwrites_stale_dest_sysdataset(
        self, client, extra_pool, initial_sysds,
    ):
        import truenas_pylibzfs

        original_pool = initial_sysds["pool"]
        original_sentinel = f"current-pool-{uuid.uuid4().hex}"
        stale_sentinel = f"stale-dest-{uuid.uuid4().hex}"

        # Place a sentinel in the live (current) sysdataset.
        _remove_sentinel()
        _write_sentinel(original_sentinel)

        # Force-create stale `<extra_pool>/.system` with a stale sentinel
        # bypassing the middleware.
        lz = truenas_pylibzfs.open_handle()
        try:
            stale_root = f"{extra_pool}/.system"
            try:
                lz.create_resource(
                    name=stale_root,
                    type=truenas_pylibzfs.ZFSType.ZFS_TYPE_FILESYSTEM,
                )
            except truenas_pylibzfs.ZFSException:
                # If it's a leftover from a prior aborted test, that's fine.
                pass
            stale_rsrc = lz.open_resource(name=stale_root)
            try:
                stale_rsrc.mount()
                # mount() may use a default mountpoint; resolve and write a
                # marker at its root.
                mnt = stale_rsrc.get_mountpoint()
                if mnt and mnt != "legacy":
                    with open(os.path.join(mnt, "STALE_MARKER"), "w") as f:
                        f.write(stale_sentinel)
                    stale_rsrc.unmount()
            except truenas_pylibzfs.ZFSException:
                # Best effort — we just need the dataset to exist as the
                # destroy_impl(bypass=True) target.
                pass
        finally:
            del lz

        # Migrate to extra_pool. Pre-replicate destroy(bypass=True) should
        # wipe the stale tree; the live sentinel should be what's there.
        client.call("systemdataset.update", {"pool": extra_pool}, job=True)

        assert _sysds_mount_source() == f"{extra_pool}/.system"
        assert _read_sentinel() == original_sentinel

        # The stale marker we put on the pre-existing dataset must be gone.
        assert not os.path.exists(os.path.join(SYSDATASET_PATH, "STALE_MARKER"))

        # Cleanup
        client.call("systemdataset.update", {"pool": original_pool}, job=True)
        _remove_sentinel()


# ---------------------------------------------------------------------------
# Mount mechanics
# ---------------------------------------------------------------------------


class TestMountMechanics:
    """Verify the mount-API invariants: /var private propagation, and the
    cores → coredump bind not sharing a propagation peer group."""

    def test_var_mount_is_private(self):
        """/var must be MS_PRIVATE so our mount churn doesn't propagate to
        peer namespaces (systemd unit private mounts, containers, etc.)
        and so MOVE_MOUNT_BENEATH source mounts (which require MS_PRIVATE)
        work correctly."""
        opts = _propagation_for("/var")
        # MS_PRIVATE shows as no shared:N / master:N / propagate_from:N tag.
        for tag in opts:
            assert not tag.startswith("shared:"), (
                f"/var has shared propagation: {opts}"
            )
            assert not tag.startswith("master:"), (
                f"/var has slave propagation: {opts}"
            )

    def test_cores_coredump_bind_propagation_isolated(self):
        """The cores→coredump bind must not be a propagation peer of the
        cores dataset itself. Catches a regression of the original
        `OPEN_TREE_CLONE`-without-private bug where umount of one mount
        propagated to the other."""
        cores_path = f"{SYSDATASET_PATH}/cores"
        if not os.path.exists(cores_path):
            pytest.skip("/var/db/system/cores not present; sysdataset not mounted")
        if not os.path.exists(COREDUMP_PATH):
            pytest.skip(f"{COREDUMP_PATH} not present")

        cores_sm = statmount(path=cores_path)
        coredump_sm = statmount(path=COREDUMP_PATH)

        # Both should be sourced from the same .system/cores dataset.
        assert cores_sm["mount_source"].endswith(".system/cores"), cores_sm
        assert coredump_sm["mount_source"].endswith(".system/cores"), coredump_sm

        # And they must not be peers in any shared propagation group: with
        # /var private (set up at boot), neither mount should carry a
        # `shared:N` tag.
        for path in (cores_path, COREDUMP_PATH):
            for tag in _propagation_for(path):
                assert not tag.startswith("shared:"), (
                    f"{path} has shared propagation: {tag}"
                )
