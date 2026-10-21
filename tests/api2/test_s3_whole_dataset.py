"""WHOLE_DATASET S3 buckets. The dataset already exists. The S3 service
serves it read-only. `sharing.s3` does not create, write to, or destroy
the dataset.

These tests cover the configuration side: what is accepted, what is
refused, what is rendered, and what other services can still do with the
dataset. What the S3 service serves is tested over the wire in
``tests/sharing_protocols/s3/test_s3_whole_dataset.py``."""

import base64
import contextlib
import json
from configparser import RawConfigParser

import pytest
from middlewared.service_exception import ValidationErrors
from middlewared.test.integration.assets.account import user
from middlewared.test.integration.assets.cloud_sync import credential as cloud_credential
from middlewared.test.integration.assets.entitlements import entitled
from middlewared.test.integration.assets.pool import dataset, pool
from middlewared.test.integration.utils import call, ssh

SERVICE = "s3"
BUCKETS_CONF = "/etc/truenas_s3/buckets.conf"
OWNER = "s3exportowner"
SIDE_TREE = ".truenas_s3"
CONFIG_BACKUP = f"{SIDE_TREE}/config_backup.json"
ROOT_XATTR = "trusted.tns3_root"
LATCH_XATTR = "trusted.tns3_latch"
LATCH_BYTES = "5453334200000001"
"""A latch record as the S3 service writes one, hex."""
PROPERTIES = ["acltype", "aclmode", "aclinherit", "xattr", "casesensitivity", "readonly", "atime"]
"""Properties that are set on a BUCKET dataset. A WHOLE_DATASET dataset must keep its own values."""


def parse(path):
    parser = RawConfigParser(interpolation=None)
    parser.read_string(ssh(f"cat {path}"))
    return {section: dict(parser[section]) for section in parser.sections()}


def rendered_row(name):
    call("etc.generate", "truenas_s3")
    return parse(BUCKETS_CONF).get(f'bucket "{name}"')


def zfs_props(name, props):
    rows = call("zfs.resource.list", {"paths": [name], "properties": props})
    return {p: rows[0]["properties"][p]["raw"] for p in props} if rows else None


def tree_of(ds):
    """Every entry under the mount point."""
    return ssh(f"cd /mnt/{ds} && find . -mindepth 1 | sort").split()


def backup_of(ds):
    raw = ssh(f"cat /mnt/{ds}/{CONFIG_BACKUP} 2>/dev/null || true")
    return json.loads(raw) if raw.strip() else None


def write_backup(ds, row):
    blob = base64.b64encode(json.dumps(row).encode()).decode()
    script = (
        f"import base64, pathlib; "
        f"pathlib.Path('/mnt/{ds}/{CONFIG_BACKUP}').write_bytes(base64.b64decode('{blob}'))"
    )
    ssh(f'python3 -c "{script}"')


@contextlib.contextmanager
def running_service():
    assert call("service.control", "START", SERVICE, {"silent": False}, job=True)
    try:
        yield
    finally:
        call("service.control", "STOP", SERVICE, {"silent": False}, job=True)


@pytest.fixture(scope="module")
def owner():
    with user({"username": OWNER, "full_name": "export owner", "group_create": True, "password": "test1234"}) as u:
        yield u


@contextlib.contextmanager
def filled_dataset(leaf="s3-export", data=None):
    """A dataset with default properties and a few files, readable by
    everyone."""
    with dataset(leaf, data) as ds:
        mount = f"/mnt/{ds}"
        ssh(
            f"mkdir -p {mount}/docs && printf alpha > {mount}/a.txt && printf bravo > {mount}/docs/b.txt"
            f" && chmod -R a+rX {mount}"
        )
        yield ds


def export_row(ds, **overrides):
    return {"name": "export", "dataset": ds, "owner": OWNER, "layout": "WHOLE_DATASET", **overrides}


@contextlib.contextmanager
def export(ds, **overrides):
    entry = call("sharing.s3.create", export_row(ds, **overrides))
    try:
        yield entry
    finally:
        with contextlib.suppress(Exception):
            call("sharing.s3.delete", entry["id"])


@contextlib.contextmanager
def plain_bucket(name="plain"):
    """A BUCKET bucket on its own dataset."""
    entry = call("sharing.s3.create", {"name": name, "dataset": f"{pool}/s3-export-{name}", "owner": OWNER})
    try:
        yield entry
    finally:
        for row in call("sharing.s3.query", [["dataset", "=", entry["dataset"]]]):
            with contextlib.suppress(Exception):
                call("sharing.s3.delete", row["id"])
        call("zfs.resource.destroy", {"path": entry["dataset"], "recursive": True})


def refused(**row):
    """The validation errors that `sharing.s3.create` raises for `row`.
    Also checks that nothing was registered."""
    with pytest.raises(ValidationErrors) as ve:
        call("sharing.s3.create", row)
    assert not call("sharing.s3.query", [["name", "=", row["name"]]])
    return ve.value.errors


def test_an_export_adopts_the_dataset_and_writes_nothing(owner):
    """Create, service start, and delete change nothing on the dataset.
    No property changes. No s3data, no .truenas_s3, no backup."""
    with filled_dataset() as ds:
        before = zfs_props(ds, PROPERTIES)
        tree = tree_of(ds)
        with export(ds) as b:
            assert b["layout"] == "WHOLE_DATASET"
            assert b["dataset"] == ds
            assert "path" not in b
            assert b["owner_uid"] == owner["uid"]
            assert (b["permissions_model"], b["object_ownership"]) == ("MULTIPROTOCOL", "OBJECT_WRITER")
            assert (b["versioning"], b["object_lock"], b["snapshot_versions"]) == ("OFF", False, [])
            assert b["locked"] is False
            assert zfs_props(ds, PROPERTIES) == before
            assert tree_of(ds) == tree
            with running_service():
                assert tree_of(ds) == tree, "the service start writes nothing"
            assert backup_of(ds) is None
            assert rendered_row("export") == {
                "dataset": ds,
                "path": f"/mnt/{ds}",
                "layout": "whole_dataset",
                "owner": OWNER,
                "owner_id": str(owner["uid"]),
                "permissions_model": "multiprotocol",
                "object_ownership": "object_writer",
                "versioning": "off",
                "multipart_etag": "minted",
                "object_lock": "off",
            }
        assert rendered_row("export") is None
        assert zfs_props(ds, ["mounted"]) == {"mounted": "yes"}
        assert tree_of(ds) == tree


def test_a_bucket_row_renders_without_a_layout_key(owner):
    with plain_bucket() as b:
        assert b["layout"] == "BUCKET"
        assert "layout" not in rendered_row("plain")


def test_a_failed_create_leaves_the_dataset_alone(owner):
    with filled_dataset() as ds:
        tree = tree_of(ds)
        (error,) = refused(**export_row(ds, owner="nosuchuser"))
        assert error.attribute == "sharing_s3_create.owner"
        assert zfs_props(ds, ["mounted"]) == {"mounted": "yes"}
        assert tree_of(ds) == tree


def test_the_permissions_model_may_be_stated(owner):
    """MULTIPROTOCOL is only the default. S3 can be set. Then only the
    grants decide who can read."""
    with filled_dataset() as ds:
        with export(ds, permissions_model="S3") as b:
            assert (b["permissions_model"], b["object_ownership"]) == ("S3", "BUCKET_OWNER_ENFORCED")
            row = rendered_row("export")
            assert (row["permissions_model"], row["object_ownership"]) == ("s3", "bucket_owner_enforced")
        with export(ds, permissions_model="MULTIPROTOCOL", object_ownership="BUCKET_OWNER_ENFORCED") as b:
            assert (b["permissions_model"], b["object_ownership"]) == ("MULTIPROTOCOL", "OBJECT_WRITER")


def test_what_an_export_cannot_serve_is_refused(owner):
    """versioning, object_lock and snapshot_versions are refused on create
    and on update, even with the versioning licence. `dataset` is
    required."""
    with filled_dataset() as ds, entitled("S3_VERSIONING"):
        for bad, field in (
            ({"versioning": "ENABLED"}, "versioning"),
            ({"versioning": "SUSPENDED"}, "versioning"),
            ({"versioning": "ENABLED", "object_lock": True}, "object_lock"),
            ({"snapshot_versions": ["*"]}, "snapshot_versions"),
        ):
            attributes = [e.attribute for e in refused(**export_row(ds, **bad))]
            assert f"sharing_s3_create.{field}" in attributes, (bad, attributes)
        (error,) = refused(**{k: v for k, v in export_row(ds).items() if k != "dataset"})
        assert error.attribute == "sharing_s3_create.dataset"
        assert "names the dataset" in error.errmsg
        with export(ds) as b:
            for bad, field in (
                ({"versioning": "ENABLED"}, "versioning"),
                ({"snapshot_versions": ["*"]}, "snapshot_versions"),
            ):
                with pytest.raises(ValidationErrors) as ve:
                    call("sharing.s3.update", b["id"], bad)
                assert f"sharing_s3_update.{field}" in [e.attribute for e in ve.value.errors]


def test_a_dataset_the_service_would_exclude_is_refused(owner):
    """Each check matches a check that the S3 service makes at
    registration. The bucket is refused here with an error. Without the
    check, the service would register the bucket and return 503."""

    def refusal(ds, **overrides):
        (error,) = refused(**export_row(ds, **overrides))
        assert error.attribute == "sharing_s3_create.dataset", error
        return error.errmsg

    assert "does not exist" in refusal(f"{pool}/s3-export-missing")
    assert "system dataset" in refusal("boot-pool/ROOT")
    with dataset("s3-export-zvol", {"type": "VOLUME", "volsize": 16 * 1024 * 1024}) as zvol:
        assert "volume" in refusal(zvol)
    with filled_dataset() as ds:
        ssh(f"zfs unmount {ds}")
        try:
            assert "not mounted" in refusal(ds)
        finally:
            ssh(f"zfs mount {ds}")
        moved = f"/mnt/{pool}/s3-export-moved"
        ssh(f"zfs set mountpoint={moved} {ds}")
        try:
            assert "is mounted at" in refusal(ds)
        finally:
            ssh(f"zfs inherit mountpoint {ds} && rmdir {moved}")
        was = zfs_props(ds, ["xattr"])["xattr"]
        ssh(f"zfs set xattr=off {ds}")
        try:
            assert "xattr=off" in refusal(ds)
        finally:
            ssh(f"zfs set xattr={was} {ds}")
        with export(ds):
            assert "already uses this dataset" in refusal(ds, name="second")
        with plain_bucket() as b:
            assert "already uses this dataset" in refusal(b["dataset"])
    locked = {
        "encryption": True,
        "inherit_encryption": False,
        "encryption_options": {"generate_key": False, "pbkdf2iters": 100000, "passphrase": "s3export-passphrase"},
    }
    with dataset("s3-export-locked", locked) as ds:
        call("pool.dataset.lock", ds, job=True)
        assert "locked" in refusal(ds)


def test_a_bucket_layout_is_refused_by_name(owner):
    """A dataset that already holds an S3 bucket is refused. Each of the
    root sentinel xattr, the latch xattr, and the .truenas_s3 directory is
    enough. The error names what was found and says to use
    sharing.s3.recover."""
    with filled_dataset() as ds:
        mount = f"/mnt/{ds}"
        def setxattr(name, value):
            return f"python3 -c 'import os; os.setxattr(\"{mount}\", \"{name}\", bytes.fromhex(\"{value}\"))'"

        def removexattr(name):
            return f"python3 -c 'import os; os.removexattr(\"{mount}\", \"{name}\")'"

        for plant, clear, named in (
            (setxattr(ROOT_XATTR, "00"), removexattr(ROOT_XATTR), ROOT_XATTR),
            (setxattr(LATCH_XATTR, LATCH_BYTES), removexattr(LATCH_XATTR), LATCH_XATTR),
            (f"mkdir -m 700 {mount}/{SIDE_TREE}", f"rmdir {mount}/{SIDE_TREE}", f"{SIDE_TREE}/"),
        ):
            ssh(plant)
            try:
                (error,) = refused(**export_row(ds))
            finally:
                ssh(clear)
            assert error.attribute == "sharing_s3_create.dataset"
            assert named in error.errmsg, error.errmsg
            assert "sharing.s3.recover" in error.errmsg
        with export(ds):
            pass


def test_a_read_only_dataset_is_admitted(owner):
    """A read-only dataset is accepted. A replication target is read-only.
    The bucket is created and rendered, and the service starts with it."""
    with filled_dataset() as ds:
        ssh(f"zfs set readonly=on {ds}")
        with export(ds):
            assert rendered_row("export")["layout"] == "whole_dataset"
            with running_service():
                assert call("service.query", [["service", "=", SERVICE]], {"get": True})["state"] == "RUNNING"


def test_a_dataset_mounted_beneath_is_admitted(owner):
    """A dataset with a child dataset mounted under it is accepted. The
    child stays mounted. The protocol suite checks that nothing in the
    child is served."""
    with filled_dataset() as ds, dataset("s3-export/child") as child:
        ssh(f"printf charlie > /mnt/{child}/c.txt")
        with export(ds) as b:
            assert rendered_row("export")["dataset"] == ds
            with running_service():
                assert call("sharing.s3.get_instance", b["id"])["enabled"] is True
            assert zfs_props(child, ["mounted"]) == {"mounted": "yes"}


def test_a_bucket_may_be_created_under_an_export(owner):
    """A BUCKET bucket can be created under a WHOLE_DATASET bucket. A share
    of the BUCKET bucket's mountpoint is refused. A share of the
    WHOLE_DATASET bucket's mountpoint is allowed."""
    with filled_dataset() as ds, export(ds):
        inner = call("sharing.s3.create", {"name": "inner", "dataset": f"{ds}/inner", "owner": OWNER})
        try:
            with pytest.raises(ValidationErrors) as ve:
                call("sharing.smb.create", {"name": "s3-inner", "path": f"/mnt/{inner['dataset']}"})
            assert ve.value.errors[0].attribute == "sharingsmb_create.path"
            assert "inner" in ve.value.errors[0].errmsg
            share = call("sharing.smb.create", {"name": "s3-export", "path": f"/mnt/{ds}"})
            call("sharing.smb.delete", share["id"])
        finally:
            call("sharing.s3.delete", inner["id"])
            call("zfs.resource.destroy", {"path": inner["dataset"], "recursive": True})


def test_other_protocols_keep_writing_an_exported_dataset(owner):
    """Shares and writing tasks are refused on a BUCKET dataset. On a
    WHOLE_DATASET dataset they are accepted, at the mountpoint and
    read-write. A recursive permissions change over the dataset is also
    allowed."""
    with filled_dataset() as ds, export(ds):
        mount = f"/mnt/{ds}"
        for api, data in (
            ("sharing.smb", {"name": "s3-export", "path": mount, "readonly": False}),
            ("sharing.nfs", {"path": mount, "ro": False}),
        ):
            share = call(f"{api}.create", data)
            call(f"{api}.delete", share["id"])
        with entitled("WEBSHARE"):
            share = call("sharing.webshare.create", {"name": "s3-export", "path": mount})
            call("sharing.webshare.delete", share["id"])

        rsync = {"user": "root", "mode": "MODULE", "remotehost": "127.0.0.1", "remotemodule": "test"}
        task = call("rsynctask.create", {**rsync, "path": mount, "direction": "PULL"})
        call("rsynctask.delete", task["id"])

        with cloud_credential(
            {"provider": {"type": "FTP", "host": "localhost", "port": 21, "user": "anonymous", "pass": ""}}
        ) as c:
            sync = {
                "description": "s3 export pull",
                "credentials": c["id"],
                "attributes": {"folder": ""},
                "transfer_mode": "COPY",
                "schedule": {"minute": "00", "hour": "00", "dom": "1", "month": "1", "dow": "1"},
            }
            task = call("cloudsync.create", {**sync, "path": mount, "direction": "PULL"})
            call("cloudsync.delete", task["id"])

        ssh(f"mkdir -p {mount}/home")
        with user(
            {
                "username": "s3exporthome",
                "full_name": "export home",
                "group_create": True,
                "password": "test1234",
                "home": f"{mount}/home",
                "home_create": False,
            }
        ):
            pass

        ftp = call("ftp.config")
        try:
            call("ftp.update", {"onlyanonymous": True, "anonpath": mount})
        finally:
            call("ftp.update", {"onlyanonymous": ftp["onlyanonymous"], "anonpath": ftp["anonpath"]})

        call("filesystem.chown", {"path": mount, "uid": 0, "options": {"recursive": True, "traverse": True}}, job=True)


def test_an_export_is_neither_backed_up_nor_recoverable(owner):
    """No backup is written by create, render or service start. After
    delete the dataset is not recoverable. A backup edited to say
    WHOLE_DATASET recovers as BUCKET."""
    with filled_dataset() as ds:
        with export(ds):
            call("etc.generate", "truenas_s3")
            with running_service():
                pass
            assert backup_of(ds) is None
            assert ssh(f"test -e /mnt/{ds}/{SIDE_TREE} || echo absent").strip() == "absent"
        assert ds not in [b["dataset"] for b in call("sharing.s3.recoverable_buckets")]
        answer = call("sharing.s3.recover", [{"dataset": ds}])[0]
        assert answer["bucket"] is None
        assert "no bucket config backup" in answer["error"]

    with plain_bucket() as b:
        call("sharing.s3.delete", b["id"])
        row = backup_of(b["dataset"])
        assert row["layout"] == "BUCKET"
        write_backup(b["dataset"], {**row, "layout": "WHOLE_DATASET"})
        answer = call("sharing.s3.recover", [{"dataset": b["dataset"]}])[0]
        assert answer["error"] is None, answer["error"]
        assert answer["bucket"]["layout"] == "BUCKET"


def test_force_disable_versioning_is_a_no_op_on_an_export(owner):
    with filled_dataset() as ds, export(ds) as b:
        entry = call("sharing.s3.force_disable_versioning", b["id"])
        assert (entry["versioning"], entry["snapshot_versions"]) == ("OFF", [])
        assert entry["layout"] == "WHOLE_DATASET"


def test_the_layout_is_create_only(owner):
    """layout cannot be changed on update. Delete the bucket and create it
    again instead."""
    with filled_dataset() as ds, export(ds) as b:
        with pytest.raises(ValidationErrors) as ve:
            call("sharing.s3.update", b["id"], {"layout": "BUCKET"})
        assert "not permitted" in ve.value.errors[0].errmsg
        assert call("sharing.s3.get_instance", b["id"])["layout"] == "WHOLE_DATASET"
    with plain_bucket() as b:
        with pytest.raises(ValidationErrors) as ve:
            call("sharing.s3.update", b["id"], {"layout": "WHOLE_DATASET"})
        assert "not permitted" in ve.value.errors[0].errmsg
        assert call("sharing.s3.get_instance", b["id"])["layout"] == "BUCKET"
