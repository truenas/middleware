import errno

import pytest

from middlewared.service_exception import CallError, ValidationError
from middlewared.test.integration.assets.pool import dataset, snapshot
from middlewared.test.integration.utils import call, pool, ssh


def test_zfs_resource_snapshot_rollback_basic():
    """Test basic rollback functionality"""
    with dataset("test_snap_rollback_basic") as ds:
        # Create snapshot
        ssh(f"zfs snapshot {ds}@snap1")

        try:
            # Create second snapshot
            ssh(f"zfs snapshot {ds}@snap2")

            # Verify both exist
            result = call("zfs.resource.snapshot.query", {"paths": [ds]})
            assert len(result) == 2

            # Rollback to snap1 with recursive (to destroy snap2)
            call(
                "zfs.resource.snapshot.rollback",
                {"path": f"{ds}@snap1", "recursive": True},
            )

            # Verify snap2 is gone
            result = call("zfs.resource.snapshot.query", {"paths": [ds]})
            assert len(result) == 1
            assert result[0]["snapshot_name"] == "snap1"
        finally:
            # Cleanup
            ssh(f"zfs destroy {ds}@snap1 2>/dev/null || true")
            ssh(f"zfs destroy {ds}@snap2 2>/dev/null || true")


def test_zfs_resource_snapshot_rollback_more_recent_snapshots():
    """Rollback without recursive must fail and list the snapshots that prevent it"""
    with dataset("test_snap_rollback_recent") as ds:
        # snap1 is the rollback target; snap2/snap3 are newer and block a
        # non-recursive rollback to snap1
        with snapshot(ds, "snap1"), snapshot(ds, "snap2"), snapshot(ds, "snap3"):
            # Rollback to snap1 without recursive should fail
            with pytest.raises(ValidationError) as ve:
                call(
                    "zfs.resource.snapshot.rollback",
                    {"path": f"{ds}@snap1"},
                )

            assert ve.value.errno == errno.EINVAL
            assert "Cannot rollback: more recent snapshots or bookmarks exist" in ve.value.errmsg
            # The error must list the snapshots that prevent the rollback
            assert f"{ds}@snap2" in ve.value.errmsg
            assert f"{ds}@snap3" in ve.value.errmsg

            # The rollback was refused up front, so nothing was destroyed
            result = call("zfs.resource.snapshot.query", {"paths": [ds]})
            assert {snap["snapshot_name"] for snap in result} == {"snap1", "snap2", "snap3"}


def test_zfs_resource_snapshot_rollback_newer_bookmark_fails_and_says_how_to_proceed():
    """A newer bookmark is not destroyed by the rollback, so the kernel refuses it and the error says so"""
    with dataset("test_snap_rollback_bookmark") as ds:
        ssh(f"zfs snapshot {ds}@snap1")
        ssh(f"zfs snapshot {ds}@snap2")
        ssh(f"zfs bookmark {ds}@snap2 {ds}#bm2")
        # Only the bookmark is left to block the rollback, so there is nothing for
        # the pre-flight to find and nothing for `recursive` to destroy
        ssh(f"zfs destroy {ds}@snap2")

        for options in ({}, {"recursive": True}):
            with pytest.raises(CallError) as ce:
                call("zfs.resource.snapshot.rollback", {"path": f"{ds}@snap1", **options})

            assert ce.value.errno == errno.EEXIST
            assert "bookmark" in ce.value.errmsg
            assert f"zfs destroy {ds}#<bookmark>" in ce.value.errmsg
            # Nothing was destroyed, so nothing can have been lost
            assert "were already destroyed" not in ce.value.errmsg
            result = call("zfs.resource.snapshot.query", {"paths": [ds]})
            assert [snap["snapshot_name"] for snap in result] == ["snap1"]

        # Removing the bookmark by hand is all the rollback was waiting for
        ssh(f"zfs destroy {ds}#bm2")
        call("zfs.resource.snapshot.rollback", {"path": f"{ds}@snap1"})


def test_zfs_resource_snapshot_rollback_newer_bookmark_fails_after_snapshots_are_destroyed():
    """`recursive` destroys the newer snapshots first, so a newer bookmark fails a committed destroy"""
    with dataset("test_snap_rollback_bookmark_destroyed") as ds:
        ssh(f"zfs snapshot {ds}@snap1")
        ssh(f"zfs snapshot {ds}@snap2")
        ssh(f"zfs bookmark {ds}@snap2 {ds}#bm2")

        with pytest.raises(CallError) as ce:
            call(
                "zfs.resource.snapshot.rollback",
                {"path": f"{ds}@snap1", "recursive": True},
            )

        assert ce.value.errno == errno.EEXIST
        assert "bookmark" in ce.value.errmsg
        # The destroy of the newer snapshots is committed before the rollback is
        # attempted, and it cannot be undone
        assert "were already destroyed" in ce.value.errmsg
        result = call("zfs.resource.snapshot.query", {"paths": [ds]})
        assert [snap["snapshot_name"] for snap in result] == ["snap1"]


def test_zfs_resource_snapshot_rollback_recursive_destroys_many_newer_snapshots():
    """Every newer snapshot goes, not just the first one"""
    with dataset("test_snap_rollback_many") as ds:
        ssh(f"zfs snapshot {ds}@snap0")
        # One snapshot per invocation, so they do not all land in the same transaction group
        ssh(f"for i in $(seq 1 10); do zfs snapshot {ds}@snap$i; done")

        call(
            "zfs.resource.snapshot.rollback",
            {"path": f"{ds}@snap0", "recursive": True},
        )

        result = call("zfs.resource.snapshot.query", {"paths": [ds]})
        assert [snap["snapshot_name"] for snap in result] == ["snap0"]


def test_zfs_resource_snapshot_rollback_path_validation():
    """Test that path validation works correctly"""
    with dataset("test_snap_rollback_validate") as ds:
        # Should fail: path without @
        with pytest.raises(Exception) as exc_info:
            call("zfs.resource.snapshot.rollback", {"path": ds})
        assert "must be a snapshot path" in str(exc_info.value).lower()

        # A path with an empty component or a second '@' is not a snapshot path
        # either, and must be refused as invalid input rather than surfacing a
        # raw ZFS open failure.
        for bad_path in (f"{ds}@", "@snap1", f"{ds}@a@b"):
            with pytest.raises(ValidationError) as ve:
                call("zfs.resource.snapshot.rollback", {"path": bad_path})
            assert ve.value.errno == errno.EINVAL
            assert "must be a snapshot path" in ve.value.errmsg


def test_zfs_resource_snapshot_rollback_nonexistent():
    """Test rollback to non-existent snapshot returns error"""
    with dataset("test_snap_rollback_noent") as ds:
        with pytest.raises(Exception) as exc_info:
            call(
                "zfs.resource.snapshot.rollback",
                {"path": f"{ds}@nonexistent"},
            )
        assert (
            "not found" in str(exc_info.value).lower()
            or "noent" in str(exc_info.value).lower()
        )


def test_zfs_resource_snapshot_rollback_protected_path():
    """Test that rollback on protected paths is rejected"""
    # boot-pool is always protected - no need to create actual resources
    with pytest.raises(Exception) as exc_info:
        call(
            "zfs.resource.snapshot.rollback",
            {"path": "boot-pool@test"},
        )
    assert "protected" in str(exc_info.value).lower()


def test_zfs_resource_snapshot_rollback_clone_blocks_recursive():
    """A clone of a newer snapshot blocks `recursive` and the error says how to proceed"""
    with dataset("test_snap_rollback_clone_blocks") as ds:
        # The clone lives under the dataset, so it is reaped by its recursive delete
        clone = f"{ds}/clone1"
        with snapshot(ds, "snap1"), snapshot(ds, "snap2"):
            ssh(f"zfs clone {ds}@snap2 {clone}")

            with pytest.raises(CallError) as ce:
                call(
                    "zfs.resource.snapshot.rollback",
                    {"path": f"{ds}@snap1", "recursive": True},
                )

            assert ce.value.errno == errno.EBUSY
            assert f"{ds}@snap2" in ce.value.errmsg
            assert clone in ce.value.errmsg
            assert "recursive_clones" in ce.value.errmsg

            # Nothing was destroyed
            result = call("zfs.resource.snapshot.query", {"paths": [ds]})
            assert {snap["snapshot_name"] for snap in result} == {"snap1", "snap2"}


def test_zfs_resource_snapshot_rollback_recursive_clones_destroys_clone():
    """`recursive_clones` destroys the clone of the newer snapshot and rolls back"""
    with dataset("test_snap_rollback_clone_destroy") as ds:
        clone = f"{ds}/clone1"
        with snapshot(ds, "snap1"), snapshot(ds, "snap2"):
            ssh(f"zfs clone {ds}@snap2 {clone}")

            call(
                "zfs.resource.snapshot.rollback",
                {"path": f"{ds}@snap1", "recursive_clones": True, "force": True},
            )

            assert ssh(f"zfs list -H -o name {clone}", check=False, complete_response=True)["result"] is False
            # Destroying the clone takes its mountpoint directory with it, so the
            # name stays free for a later create
            assert ssh(f"test -d /mnt/{clone}", check=False, complete_response=True)["result"] is False
            result = call("zfs.resource.snapshot.query", {"paths": [ds]})
            assert [snap["snapshot_name"] for snap in result] == ["snap1"]


def test_zfs_resource_snapshot_rollback_recursive_clones_without_force_destroys_mounted_clone():
    """A mounted clone is unmounted and destroyed even when `force` is not passed"""
    with dataset("test_snap_rollback_clone_noforce") as ds:
        clone = f"{ds}/clone1"
        with snapshot(ds, "snap1"), snapshot(ds, "snap2"):
            ssh(f"zfs clone {ds}@snap2 {clone}")
            # The clone has to actually be mounted for this test to mean anything
            assert ssh(f"mountpoint -q /mnt/{clone}", check=False, complete_response=True)["result"] is True

            call(
                "zfs.resource.snapshot.rollback",
                {"path": f"{ds}@snap1", "recursive_clones": True},
            )

            assert ssh(f"zfs list -H -o name {clone}", check=False, complete_response=True)["result"] is False
            result = call("zfs.resource.snapshot.query", {"paths": [ds]})
            assert [snap["snapshot_name"] for snap in result] == ["snap1"]


def test_zfs_resource_snapshot_rollback_nested_clone_refused():
    """A clone that has descendants of its own cannot be destroyed, so the rollback is refused"""
    with dataset("test_snap_rollback_nested_clone") as ds:
        clone = f"{ds}/clone1"
        with snapshot(ds, "snap1"), snapshot(ds, "snap2"):
            ssh(f"zfs clone {ds}@snap2 {clone}")
            try:
                ssh(f"zfs snapshot {clone}@c1")

                with pytest.raises(CallError) as ce:
                    call(
                        "zfs.resource.snapshot.rollback",
                        {"path": f"{ds}@snap1", "recursive_clones": True, "force": True},
                    )

                assert ce.value.errno == errno.EBUSY
                assert clone in ce.value.errmsg
                assert f"{clone}@c1" in ce.value.errmsg

                # Nothing was destroyed
                assert ssh(f"zfs list -H -o name {clone}", check=False, complete_response=True)["result"] is True
                result = call("zfs.resource.snapshot.query", {"paths": [ds]})
                assert {snap["snapshot_name"] for snap in result} == {"snap1", "snap2"}
            finally:
                # A clone holding its own snapshot cannot be torn down by the
                # snapshot fixture, so remove it here
                ssh(f"zfs destroy -r {clone} || true")


def test_zfs_resource_snapshot_rollback_hold_blocks_rollback():
    """A hold on a newer snapshot blocks the rollback and the error names the tag"""
    with dataset("test_snap_rollback_hold") as ds:
        with snapshot(ds, "snap1"), snapshot(ds, "snap2"):
            ssh(f"zfs hold truenas {ds}@snap2")

            with pytest.raises(CallError) as ce:
                call(
                    "zfs.resource.snapshot.rollback",
                    {"path": f"{ds}@snap1", "recursive": True},
                )

            assert ce.value.errno == errno.EBUSY
            assert f"{ds}@snap2" in ce.value.errmsg
            assert "truenas" in ce.value.errmsg

            result = call("zfs.resource.snapshot.query", {"paths": [ds]})
            assert {snap["snapshot_name"] for snap in result} == {"snap1", "snap2"}


def test_zfs_resource_snapshot_rollback_snapshot_in_use_blocks_rollback():
    """A snapshot the kernel holds open is reported from the kernel's own error list"""
    with dataset("test_snap_rollback_in_use") as ds:
        with snapshot(ds, "snap1"), snapshot(ds, "snap2"):
            # Walking into .zfs/snapshot automounts snap2, and the kernel long-holds a
            # snapshot for as long as it is mounted. The pre-flight cannot see that hold:
            # get_holds() only reports user holds.
            ssh(f"ls /mnt/{ds}/.zfs/snapshot/snap2")

            try:
                with pytest.raises(CallError) as ce:
                    call(
                        "zfs.resource.snapshot.rollback",
                        {"path": f"{ds}@snap1", "recursive": True},
                    )

                assert ce.value.errno == errno.EBUSY
                assert "is in use and cannot be destroyed" in ce.value.errmsg
                assert f"{ds}@snap2" in ce.value.errmsg
            finally:
                # The automount has to go, or the teardown cannot destroy snap2 either
                ssh(f"umount /mnt/{ds}/.zfs/snapshot/snap2", check=False)


def test_zfs_resource_snapshot_rollback_recursive_rollback_child_blocker_leaves_parent_intact():
    """A blocker on a child dataset must be found before the parent is rolled back"""
    with dataset("test_snap_rollback_child_blocker") as ds:
        child = f"{ds}/child"
        # The clone lives outside the dataset on purpose: one inside it would be
        # collected as a child of the recursive rollback and rejected for not
        # having the target snapshot, which is not what this test is about
        clone = f"{pool}/test_snap_rollback_child_blocker_clone"
        try:
            ssh(f"zfs create {child}")
            ssh(f"zfs snapshot -r {ds}@snap1")
            ssh(f"touch /mnt/{ds}/marker")
            ssh(f"zfs snapshot {child}@snap2")
            ssh(f"zfs clone {child}@snap2 {clone}")

            with pytest.raises(CallError) as ce:
                call(
                    "zfs.resource.snapshot.rollback",
                    {"path": f"{ds}@snap1", "recursive": True, "recursive_rollback": True},
                )

            assert ce.value.errno == errno.EBUSY
            assert f"{child}@snap2" in ce.value.errmsg
            assert clone in ce.value.errmsg

            # The parent was not rolled back on the way to discovering the blocker
            ssh(f"test -f /mnt/{ds}/marker")
        finally:
            ssh(f"zfs destroy -r {clone} || true")


def test_zfs_resource_snapshot_rollback_reports_every_blocker_at_once():
    """Blockers on different snapshots are all reported, not just the first one hit"""
    with dataset("test_snap_rollback_multi_blocker") as ds:
        clone = f"{ds}/clone1"
        with snapshot(ds, "snap1"), snapshot(ds, "snap2"), snapshot(ds, "snap3"):
            ssh(f"zfs clone {ds}@snap2 {clone}")
            ssh(f"zfs hold truenas {ds}@snap3")

            with pytest.raises(CallError) as ce:
                call(
                    "zfs.resource.snapshot.rollback",
                    {"path": f"{ds}@snap1", "recursive": True},
                )

            assert ce.value.errno == errno.EBUSY
            assert f"{ds}@snap2" in ce.value.errmsg
            assert clone in ce.value.errmsg
            assert f"{ds}@snap3" in ce.value.errmsg
            assert "truenas" in ce.value.errmsg


def test_zfs_resource_snapshot_rollback_clone_blocker_list_is_truncated():
    """A clone with more descendants than the report limit says the list is incomplete"""
    with dataset("test_snap_rollback_truncated") as ds:
        clone = f"{ds}/clone1"
        with snapshot(ds, "snap1"), snapshot(ds, "snap2"):
            ssh(f"zfs clone {ds}@snap2 {clone}")
            try:
                for i in range(6):
                    ssh(f"zfs create {clone}/child{i}")

                with pytest.raises(CallError) as ce:
                    call(
                        "zfs.resource.snapshot.rollback",
                        {"path": f"{ds}@snap1", "recursive_clones": True},
                    )

                assert ce.value.errno == errno.EBUSY
                assert "and more" in ce.value.errmsg
            finally:
                ssh(f"zfs destroy -r {clone} || true")


def test_zfs_resource_snapshot_rollback_recursive_rollback_rolls_back_children():
    """`recursive_rollback` rolls the child datasets back, not only the parent"""
    with dataset("test_snap_rollback_recursive_children") as ds:
        child = f"{ds}/child"
        ssh(f"zfs create {child}")
        ssh(f"zfs snapshot -r {ds}@snap1")
        ssh(f"touch /mnt/{ds}/parent_marker /mnt/{child}/child_marker")

        call(
            "zfs.resource.snapshot.rollback",
            {"path": f"{ds}@snap1", "recursive_rollback": True},
        )

        assert ssh(f"test -f /mnt/{ds}/parent_marker", check=False, complete_response=True)["result"] is False
        assert ssh(f"test -f /mnt/{child}/child_marker", check=False, complete_response=True)["result"] is False


def test_zfs_resource_snapshot_rollback_recursive_rollback_missing_child_snapshot():
    """A child that lacks the target snapshot is caught before anything is rolled back"""
    with dataset("test_snap_rollback_missing_child") as ds:
        child = f"{ds}/child"
        ssh(f"zfs create {child}")
        # Deliberately not recursive, so the child never gets snap1
        ssh(f"zfs snapshot {ds}@snap1")
        ssh(f"touch /mnt/{ds}/marker")

        with pytest.raises(ValidationError) as ve:
            call(
                "zfs.resource.snapshot.rollback",
                {"path": f"{ds}@snap1", "recursive_rollback": True},
            )

        assert ve.value.errno == errno.ENOENT
        assert f"{child}@snap1" in ve.value.errmsg

        # The parent was not rolled back on the way to discovering the missing child
        ssh(f"test -f /mnt/{ds}/marker")


def test_zfs_resource_snapshot_rollback_recursive_rollback_refuses_before_parent_is_rolled_back():
    """A newer snapshot on a child is reported before the parent is rolled back"""
    with dataset("test_snap_rollback_child_conflict") as ds:
        child = f"{ds}/child"
        ssh(f"zfs create {child}")
        ssh(f"zfs snapshot -r {ds}@snap1")
        ssh(f"touch /mnt/{ds}/marker")
        ssh(f"zfs snapshot {child}@snap2")

        with pytest.raises(ValidationError) as ve:
            call(
                "zfs.resource.snapshot.rollback",
                {"path": f"{ds}@snap1", "recursive_rollback": True},
            )

        assert ve.value.errno == errno.EINVAL
        assert f"{child}@snap2" in ve.value.errmsg

        # The parent was not rolled back on the way to discovering the conflict
        ssh(f"test -f /mnt/{ds}/marker")


def test_zfs_resource_snapshot_rollback_thick_zvol_keeps_refreservation():
    """A rollback that shrinks the volsize of a thick volume brings its refreservation along"""
    # A volume created through the middleware gets `refreservation` set to the literal
    # volsize, which is the shape the rollback restores. `zfs create -V` would instead
    # give it a larger synthetic refreservation, which is deliberately left alone.
    with dataset("test_snap_rollback_thick_zvol", {"type": "VOLUME", "volsize": 64 * 1024 ** 2}) as vol:
        ssh(f"zfs snapshot {vol}@snap1")
        ssh(f"zfs set volsize={128 * 1024 ** 2} {vol}")
        # Growing the volsize recomputes the refreservation, so put it back to the
        # literal volsize the middleware would have used
        ssh(f"zfs set refreservation={128 * 1024 ** 2} {vol}")

        # snap1 is the only snapshot, so there is nothing newer to destroy
        call("zfs.resource.snapshot.rollback", {"path": f"{vol}@snap1"})

        assert int(ssh(f"zfs get -Hp -o value volsize {vol}").strip()) == 64 * 1024 ** 2
        assert int(ssh(f"zfs get -Hp -o value refreservation {vol}").strip()) == 64 * 1024 ** 2


def test_zfs_resource_snapshot_rollback_sparse_zvol_stays_thin():
    """A sparse volume is not given a refreservation by the rollback"""
    with dataset(
        "test_snap_rollback_sparse_zvol",
        {"type": "VOLUME", "volsize": 64 * 1024 ** 2, "sparse": True},
    ) as vol:
        ssh(f"zfs snapshot {vol}@snap1")
        ssh(f"zfs set volsize={128 * 1024 ** 2} {vol}")
        assert int(ssh(f"zfs get -Hp -o value refreservation {vol}").strip()) == 0

        call("zfs.resource.snapshot.rollback", {"path": f"{vol}@snap1"})

        assert int(ssh(f"zfs get -Hp -o value refreservation {vol}").strip()) == 0


def test_zfs_resource_snapshot_rollback_zvol_clone_destroyed():
    """A cloned volume has no mountpoint to unmount, and is still destroyed"""
    with dataset("test_snap_rollback_zvol") as ds:
        vol = f"{ds}/vol"
        clone = f"{pool}/test_snap_rollback_zvol_clone"
        try:
            ssh(f"zfs create -s -V 64M {vol}")
            ssh(f"zfs snapshot {vol}@snap1")
            ssh(f"zfs snapshot {vol}@snap2")
            ssh(f"zfs clone {vol}@snap2 {clone}")

            call(
                "zfs.resource.snapshot.rollback",
                {"path": f"{vol}@snap1", "recursive_clones": True},
            )

            assert ssh(f"zfs list -H -o name {clone}", check=False, complete_response=True)["result"] is False
            result = call("zfs.resource.snapshot.query", {"paths": [vol]})
            assert [snap["snapshot_name"] for snap in result] == ["snap1"]
        finally:
            ssh(f"zfs destroy -r {clone} || true")


def test_zfs_resource_snapshot_rollback_app_flag_combination():
    """The flag combination app rollbacks send must still complete with a clone present"""
    with dataset("test_snap_rollback_app_flags") as ds:
        clone = f"{pool}/test_snap_rollback_app_flags_clone"
        try:
            ssh(f"zfs snapshot {ds}@snap1")
            ssh(f"zfs snapshot {ds}@snap2")
            ssh(f"zfs clone {ds}@snap2 {clone}")

            call(
                "zfs.resource.snapshot.rollback",
                {
                    "path": f"{ds}@snap1",
                    "recursive": True,
                    "recursive_clones": True,
                    "recursive_rollback": True,
                    "force": True,
                },
            )

            assert ssh(f"zfs list -H -o name {clone}", check=False, complete_response=True)["result"] is False
            result = call("zfs.resource.snapshot.query", {"paths": [ds]})
            assert [snap["snapshot_name"] for snap in result] == ["snap1"]
        finally:
            ssh(f"zfs destroy -r {clone} || true")
