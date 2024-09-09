import enum

import pytest

from auto_config import pool_name
from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.assets.pool import dataset

ACLTEST_DATASET_NAME = "posixacltest"
ACLTEST_DATASET_ABS_PATH = f"/mnt/{pool_name}/{ACLTEST_DATASET_NAME}"
ACLTEST_SUBDATASET_NAME = "sub1"
ACLTEST_SUBDATASET_ABS_PATH = f"{ACLTEST_DATASET_ABS_PATH}/{ACLTEST_SUBDATASET_NAME}"
PERMSET_EMPTY = {"READ": False, "WRITE": False, "EXECUTE": False}
PERMSET_FULL = {"READ": True, "WRITE": True, "EXECUTE": True}
TAGS = {
    "USER_OBJ": {"mask_required": False},
    "GROUP_OBJ": {"mask_required": False},
    "MASK": {"mask_required": False},
    "USER": {"mask_required": True},
    "GROUP": {"mask_required": True},
    "OTHER": {"mask_required": False},
}


class ACLBrand(enum.Enum):
    ACCESS = enum.auto()
    DEFAULT = enum.auto()

    def getacl(self, perms=None):
        """Default to 770 unless permissions explicitly specified."""
        permfull = perms if perms else PERMSET_FULL.copy()
        permempty = perms if perms else PERMSET_EMPTY.copy()
        default = self.name == "DEFAULT"
        return [
            {
                "tag": "USER_OBJ",
                "id": -1,
                "perms": permfull,
                "default": default,
            },
            {
                "tag": "GROUP_OBJ",
                "id": -1,
                "perms": permfull,
                "default": default,
            },
            {
                "tag": "OTHER",
                "id": -1,
                "perms": permempty,
                "default": default,
            },
        ]


@pytest.fixture(scope="module")
def temp_ds():
    with dataset(
        ACLTEST_DATASET_NAME, data={"acltype": "POSIX", "aclmode": "DISCARD"}
    ) as ds:
        # Verify that our dataset was created successfully
        # and that the acltype is POSIX1E, which should be
        # default for a "generic" dataset.
        info = call("filesystem.getacl", ACLTEST_DATASET_ABS_PATH)
        assert info["acltype"] == "POSIX1E", info

        # Verify that we can set a trivial POSIX1E ACL
        call(
            "filesystem.setacl",
            {
                "path": ACLTEST_DATASET_ABS_PATH,
                "dacl": ACLBrand.ACCESS.getacl(),
                "gid": 65534,
                "uid": 65534,
                "acltype": "POSIX1E",
            },
            job=True,
        )

        # Verify ACL is repoted as trivial
        info = call("filesystem.getacl", ACLTEST_DATASET_ABS_PATH)
        assert info["trivial"], info

        # Verify UID/GID
        assert info["uid"] == 65534, info
        assert info["gid"] == 65534, info

        # Verify ACL was applied correctly
        default_acl = ACLBrand.ACCESS.getacl()
        for idx, acl in enumerate(info["acl"]):
            for key in ("tag", "perms"):
                assert acl[key] == default_acl[idx][key], acl[key]

        # create subdataset for inheritance related tests
        call(
            "pool.dataset.create",
            {
                "name": f"{ds}/{ACLTEST_SUBDATASET_NAME}",
                "acltype": "POSIX",
                "aclmode": "DISCARD",
            },
        )
        rv = ssh(
            "; ".join(
                [
                    f"mkdir -p {ACLTEST_DATASET_ABS_PATH}/dir1/dir2",
                    f"touch {ACLTEST_DATASET_ABS_PATH}/dir1/testfile",
                    f"touch {ACLTEST_DATASET_ABS_PATH}/dir1/dir2/testfile",
                ]
            ),
            complete_response=True,
        )
        assert rv["result"] is True, rv["output"]

        yield


"""
At this point very basic functionality of API endpoint is verified.
Proceed to more rigorous testing of permissions.
"""


@pytest.mark.parametrize("perm", ["READ", "WRITE", "EXECUTE"])
def test_set_perms_for(temp_ds, perm):
    """
    Validation that READ, WRITE, EXECUTE are set correctly via endpoint.
    OTHER entry is used for this purpose.
    """
    dacls = ACLBrand.ACCESS.getacl()
    dacls[2]["perms"][perm] = True
    call(
        "filesystem.setacl",
        {"path": ACLTEST_DATASET_ABS_PATH, "dacl": dacls, "acltype": "POSIX1E"},
        job=True,
    )
    rv = call("filesystem.getacl", ACLTEST_DATASET_ABS_PATH)["acl"][2]["perms"]
    assert rv[perm], rv


@pytest.mark.parametrize("tag", TAGS.keys())
def test_set_tag_(temp_ds, tag):
    """
    Validation that entries for all tag types can be set correctly.
    In case of USER_OBJ, GROUP_OBJ, and OTHER, the existing entry
    is modified to match our test permset. USER and GROUP (named)
    entries are set for id 1000 (user / group need not exist for
    this to succeed). Named entries require an additional mask entry.
    """
    test_permset = {"READ": True, "WRITE": False, "EXECUTE": True}
    must_add = True
    payload = {
        "path": ACLTEST_DATASET_ABS_PATH,
        "dacl": ACLBrand.ACCESS.getacl(),
        "acltype": "POSIX1E",
    }
    for entry in payload["dacl"]:
        if entry["tag"] == tag:
            entry["perms"] = test_permset
            must_add = False
            break

    if must_add:
        new_entry = {
            "tag": tag,
            "perms": test_permset,
            "id": 1000,
            "default": False,
        }
        if tag == "MASK":
            new_entry["id"] = -1
            # POSIX ACLs are quite particular about
            # ACE ordering. We do this on backend.
            # MASK comes before OTHER.
            payload["dacl"].insert(2, new_entry)
        elif tag == "USER":
            payload["dacl"].insert(1, new_entry)
        elif tag == "GROUP":
            payload["dacl"].insert(2, new_entry)

    if TAGS[tag]["mask_required"]:
        new_entry = {
            "tag": "MASK",
            "perms": test_permset,
            "id": -1,
            "default": False,
        }
        payload["dacl"].insert(3, new_entry)

    call("filesystem.setacl", payload, job=True)
    rv = call("filesystem.getacl", ACLTEST_DATASET_ABS_PATH)
    assert payload["dacl"] == rv["acl"], rv


@pytest.mark.parametrize("tag", TAGS.keys())
def test_set_default_tag_(temp_ds, tag):
    """
    Validation that entries for all tag types can be set correctly.
    In case of USER_OBJ, GROUP_OBJ, and OTHER, the existing entry
    is modified to match our test permset. USER and GROUP (named)
    entries are set for id 1000 (user / group need not exist for
    this to succeed). Named entries require an additional mask entry.
    This particular test covers "default" entries in POSIX1E ACL.
    """
    test_permset = {"READ": True, "WRITE": False, "EXECUTE": True}
    must_add = True
    payload = {
        "path": ACLTEST_DATASET_ABS_PATH,
        "dacl": ACLBrand.ACCESS.getacl(),
        "acltype": "POSIX1E",
    }
    default = ACLBrand.DEFAULT.getacl()
    for entry in default:
        if entry["tag"] == tag:
            entry["perms"] = test_permset
            must_add = False

    if must_add:
        new_entry = {
            "tag": tag,
            "perms": test_permset,
            "id": 1000,
            "default": True,
        }
        if tag == "MASK":
            new_entry["id"] = -1
            # POSIX ACLs are quite particular about
            # ACE ordering. We do this on backend.
            # MASK comes before OTHER.
            default.insert(2, new_entry)
        elif tag == "USER":
            default.insert(1, new_entry)
        elif tag == "GROUP":
            default.insert(2, new_entry)

    if TAGS[tag]["mask_required"]:
        new_entry = {
            "tag": "MASK",
            "perms": test_permset,
            "id": -1,
            "default": True,
        }
        default.insert(3, new_entry)

    payload["dacl"].extend(default)
    call("filesystem.setacl", payload, job=True)
    rv = call("filesystem.getacl", ACLTEST_DATASET_ABS_PATH)
    assert payload["dacl"] == rv["acl"], rv
    assert rv["trivial"] is False, rv


def test_non_recursive_acl_strip(temp_ds):
    """
    Verify that non-recursive ACL strip works correctly.
    We do this by checking result of subsequent getacl
    request on the path (it should report that it is "trivial").
    """
    call(
        "filesystem.setacl",
        {
            "path": ACLTEST_DATASET_ABS_PATH,
            "dacl": [],
            "acltype": "POSIX1E",
            "options": {"stripacl": True},
        },
        job=True,
    )
    rv = call("filesystem.getacl", ACLTEST_DATASET_ABS_PATH)
    assert rv["trivial"] is True, rv


"""
This next series of tests verifies that ACLs are being inherited correctly.
We first create a child dataset to verify that ACLs do not change unless
'traverse' is set.
"""


def test_recursive_no_traverse(temp_ds):
    """
    Test that ACL is recursively applied correctly, but does
    not affect mountpoint of child dataset.

    In this case, access ACL will have 750 for dataset mountpoint,
    and default ACL will have 777. Recusively applying will grant
    777 for access and default.
    """
    payload = {
        "path": ACLTEST_DATASET_ABS_PATH,
        "gid": 65534,
        "uid": 65534,
        "dacl": ACLBrand.ACCESS.getacl(),
        "acltype": "POSIX1E",
        "options": {"recursive": True},
    }
    new_perms = {"READ": True, "WRITE": True, "EXECUTE": True}
    default = ACLBrand.DEFAULT.getacl(new_perms)
    payload["dacl"].extend(default)
    call("filesystem.setacl", payload, job=True)

    # Verify that subdataset hasn't changed. Should still report as trivial.
    rv = call("filesystem.getacl", ACLTEST_SUBDATASET_ABS_PATH)
    assert rv["trivial"], rv

    # Verify that user was changed on subdirectory
    rv = call("filesystem.getacl", f"{ACLTEST_DATASET_ABS_PATH}/dir1")
    assert rv["uid"] == 65534, rv
    assert rv["trivial"] is False, rv
    for entry in rv["acl"]:
        assert entry["perms"] == new_perms, rv["acl"]


def test_recursive_with_traverse(temp_ds):
    """
    This test verifies that setting `traverse = True`
    will allow setacl operation to cross mountpoints.
    """
    payload = {
        "gid": 65534,
        "uid": 65534,
        "path": ACLTEST_DATASET_ABS_PATH,
        "dacl": ACLBrand.ACCESS.getacl(),
        "acltype": "POSIX1E",
        "options": {"recursive": True, "traverse": True},
    }
    default = ACLBrand.DEFAULT.getacl({"READ": True, "WRITE": True, "EXECUTE": True})
    payload["dacl"].extend(default)
    call("filesystem.setacl", payload, job=True)
    rv = call("filesystem.getacl", ACLTEST_SUBDATASET_ABS_PATH)
    assert rv["trivial"] is False, rv
    assert rv["uid"] == 65534, rv


def test_strip_acl_from_dataset(temp_ds):
    """
    Strip ACL via filesystem.setperm endpoint.
    This should work even for POSIX1E ACLs.
    """
    call(
        "filesystem.setperm",
        {
            "path": ACLTEST_DATASET_ABS_PATH,
            "mode": "777",
            "options": {"stripacl": True, "recursive": True},
        },
        job=True,
    )


"""
The next four tests check that we've remotved the ACL from the
mountpoint, a subdirectory, and a file. These are all potentially
different cases for where we can fail to strip an ACL.
"""


def test_filesystem_acl_is_not_removed_child_dataset(temp_ds):
    rv = call("filesystem.stat", ACLTEST_SUBDATASET_ABS_PATH)
    assert rv["acl"] is True, rv


def test_filesystem_acl_is_removed_from_mountpoint(temp_ds):
    rv = call("filesystem.stat", ACLTEST_DATASET_ABS_PATH)
    assert rv["acl"] is False, rv
    assert oct(rv["mode"]) == "0o40777", rv


def test_filesystem_acl_is_removed_from_subdir(temp_ds):
    rv = call("filesystem.stat", f"{ACLTEST_DATASET_ABS_PATH}/dir1")
    assert rv["acl"] is False, rv
    assert oct(rv["mode"]) == "0o40777", rv


def test_filesystem_acl_is_removed_from_file(temp_ds):
    rv = call("filesystem.stat", f"{ACLTEST_DATASET_ABS_PATH}/dir1/testfile")
    assert rv["acl"] is False, rv
    assert oct(rv["mode"]) == "0o100777", rv
