from __future__ import annotations

import asyncio
from collections.abc import Mapping
import errno
import ipaddress
import os
import string
from types import MappingProxyType
import typing
from typing import TYPE_CHECKING, Any, Literal, TypeVar

from truenas_pylicensed.features import LicenseFeature

from middlewared.api import api_method
from middlewared.api.current import (
    S3AuditAction,
    S3BucketLayout,
    S3Entry,
    SharingS3AuditChoicesArgs,
    SharingS3AuditChoicesResult,
    SharingS3Create,
    SharingS3CreateArgs,
    SharingS3CreateResult,
    SharingS3DeleteArgs,
    SharingS3DeleteResult,
    SharingS3Entry,
    SharingS3ForceDisableVersioningArgs,
    SharingS3ForceDisableVersioningResult,
    SharingS3RecoverableBucket,
    SharingS3RecoverableBucketsArgs,
    SharingS3RecoverableBucketsResult,
    SharingS3RecoverArgs,
    SharingS3RecoverBucket,
    SharingS3RecoveredBucket,
    SharingS3RecoverResult,
    SharingS3Update,
    SharingS3UpdateArgs,
    SharingS3UpdateResult,
    ZFSResourceCreateArgsData,
    ZFSResourceCreateProperties,
    ZFSResourceQuery,
)
from middlewared.async_validators import check_path_resides_within_volume
from middlewared.common.attachment import LockableFSAttachmentDelegate
from middlewared.plugins.zfs.exceptions import (
    ZFSDestroyFailedException,
    ZFSPathAlreadyExistsException,
    ZFSPathNotFoundException,
)
from middlewared.plugins.zfs.utils import has_internal_path
from middlewared.service import CallError, SharingService, ValidationError, ValidationErrors, private
import middlewared.sqlalchemy as sa
from middlewared.utils.filter_list import filter_list
from middlewared.utils.path import FSLocation
from middlewared.utils.types import AuditCallback

from .grants import PrincipalNames, Principals, grant_principals, label_grants, principal_names, validate_grants
from .lifecycle import MISSING_ALERT, render_and_apply
from .on_disk import (
    CONFIG_BACKUP,
    SIDE_TREE,
    bucket_layout_markers,
    has_latch,
    read_config_backup,
    write_config_backup,
)

if TYPE_CHECKING:
    from middlewared.main import Middleware

__all__ = ("SharingS3Service", "S3FSAttachmentDelegate")

AUDIT_ACTIONS: tuple[str, ...] = typing.get_args(S3AuditAction)

BUCKET_LOCK = asyncio.Lock()
"""Serializes bucket registry mutations. Taken before lifecycle's render lock."""


EntryT = TypeVar("EntryT", bound=SharingS3Entry)

MANAGED_NAME_MAX_SUFFIX = 10
"""We append an `_N` suffix on collision when users create new buckets through the S3 API.
We set an upper bound of 10 because we don't want a pathologically broken script creating infinite datasets
on TrueNAS, but in theory we can increase this. I think it's most likely to happen if someone writes a dumb
CI workflow that rapidly creates / deletes buckets over S3 protocol without doing any server-side maintenance.
Obviously, we don't want to wire S3 bucket deletion into actual dataset destruction and so unmanaged churn will
eventually hit an admin-facing error here."""

SHARE_ROOT = "s3data"
"""The directory under a bucket's mount point that holds its objects when layout is `BUCKET`."""


class BucketPath(typing.NamedTuple):
    """A path's location on a bucket's dataset, as returned by `bucket_of_path`."""

    name: str
    dataset: str
    within: str
    """The path within the bucket's dataset, empty at its mount point."""


def bucket_dataset_properties() -> ZFSResourceCreateProperties:
    """These are our current defaults for new S3 buckets, and should be updated as we have more user feedback."""
    return ZFSResourceCreateProperties(
        # the first three are create-time only and would otherwise inherit
        # from the parent; the daemon never re-checks any of them
        casesensitivity="sensitive",
        normalization="none",
        utf8only="off",
        xattr="sa",
        acltype="nfsv4",
        aclmode="restricted",
        aclinherit="passthrough",
    )


BUCKET_DATASET_PROPERTIES: Mapping[str, str] = MappingProxyType(
    bucket_dataset_properties().model_dump(exclude_unset=True)
)


CREATE_TIME_PROPERTIES = frozenset({"casesensitivity", "normalization", "utf8only"})


class SharingS3Model(sa.Model):
    __tablename__ = "truenas_s3_bucket"

    id = sa.Column(sa.Integer(), primary_key=True)
    name = sa.Column(sa.String(63), unique=True)
    dataset = sa.Column(sa.String(255), unique=True)
    layout = sa.Column(sa.String(16))
    enabled = sa.Column(sa.Boolean())
    owner_uid = sa.Column(sa.Integer())
    grants = sa.Column(sa.JSON(list))
    permissions_model = sa.Column(sa.String(32))
    object_ownership = sa.Column(sa.String(32))
    versioning = sa.Column(sa.String(16))
    snapshot_versions = sa.Column(sa.JSON(list))
    snapshot_versions_max = sa.Column(sa.Integer())
    multipart_etag = sa.Column(sa.String(16))
    object_lock = sa.Column(sa.Boolean())
    object_lock_default_mode = sa.Column(sa.String(16), nullable=True)
    object_lock_default_days = sa.Column(sa.Integer(), nullable=True)
    audit = sa.Column(sa.JSON(None), nullable=True)
    audit_overflow = sa.Column(sa.String(16), nullable=True)


SNAPSHOT_PATTERN_CHARS = frozenset(string.ascii_letters + string.digits + "-_.: *?")


def is_ipv4_shaped(name: str) -> bool:
    """Fast check to prevent users from setting IP addresses as names. Symmetry with the s3 daemon"""
    try:
        ipaddress.IPv4Address(name)
    except ValueError:
        return False
    return True


MOUNTED_FILESYSTEM = (
    ("type", "=", "FILESYSTEM"),
    ("properties.mounted.raw", "=", "yes"),
    ("properties.mountpoint.raw", "^", "/"),
)

RECOVER_PROPERTIES = (
    "mountpoint",
    "mounted",
    "readonly",
    "snapdir",
    *BUCKET_DATASET_PROPERTIES,
)


def read_config_backups(mounts: dict[str, str]) -> list[dict[str, Any]]:
    """Generate a list of backup configuration read from mounted datasets. We keep a backup of
    the database row in JSON form inside the hidden .truenas_s3 dir for BUCKET layout datasets."""
    found = []
    for dataset, mount in sorted(mounts.items()):
        try:
            row = read_config_backup(mount)
        except OSError:
            continue
        if row is not None:
            found.append({k: v for k, v in row.items() if k != "version_number"} | {"dataset": dataset})
    return found


def write_config_backups(work: list[tuple[str, dict[str, Any]]]) -> list[tuple[str, Exception]]:
    failures = []
    for mount, row in work:
        try:
            stored = read_config_backup(mount)
            if stored is not None and {k: v for k, v in stored.items() if k != "version_number"} == row:
                continue
            write_config_backup(mount, row)
        except Exception as e:
            failures.append((mount, e))
    return failures


def recovery_blockers(properties: dict[str, Any], mounted_children: list[str]) -> list[str]:
    """Why the S3 service could not serve this dataset. Each mirrors a check it makes when it registers a bucket."""
    def raw(name: str) -> str | None:
        prop = properties.get(name)
        return prop["raw"] if prop else None

    blockers: list[str] = []
    if raw("readonly") == "on":
        blockers.append("The dataset is read-only.")
    for name, wanted in BUCKET_DATASET_PROPERTIES.items():
        found = raw(name)
        if found == wanted:
            continue
        if name in CREATE_TIME_PROPERTIES:
            blockers.append(
                f"{name} is {found!r} rather than {wanted!r}, and is set only at creation: this dataset cannot "
                f"hold the S3 on-disk format."
            )
        else:
            blockers.append(f"{name} is {found!r} rather than {wanted!r}. Set it and retry.")
    if mounted_children:
        blockers.append("A dataset is mounted beneath it: " + ", ".join(sorted(mounted_children)))
    return blockers


class SharingS3Service(SharingService[SharingS3Entry]):
    include_tier_info = True
    share_task_type = "S3"
    allowed_path_types = [FSLocation.LOCAL]

    class Config:
        namespace = "sharing.s3"
        datastore = "truenas_s3.bucket"
        cli_namespace = "sharing.s3"
        role_prefix = "SHARING_S3"
        generic = True
        entry = SharingS3Entry
        datastore_extend = "sharing.s3.bucket_extend"
        datastore_extend_context = "sharing.s3.bucket_extend_context"

    @private
    async def get_path_field(self, data: SharingS3Entry | dict[str, Any]) -> str:
        dataset = data["dataset"] if isinstance(data, dict) else data.dataset
        return f"/mnt/{dataset}"

    @private
    async def bucket_extend_context(self, rows: list[dict[str, Any]], extra: dict[str, Any]) -> PrincipalNames:
        """Every owner and grant principal across the rows, resolved once each rather than once per row."""
        principals = Principals(uids=frozenset(row["owner_uid"] for row in rows), gids=frozenset())
        for row in rows:
            principals |= grant_principals(row["grants"])
        return await principal_names(self.middleware, principals)

    @private
    async def bucket_extend(self, data: dict[str, Any], names: PrincipalNames) -> dict[str, Any]:
        data["owner"] = names.user(data["owner_uid"])
        data["grants"] = label_grants(data["grants"], names)
        return data

    @private
    async def validate(
        self, data: SharingS3Entry, schema: str, verrors: ValidationErrors, old: SharingS3Entry | None = None
    ) -> None:
        if ".." in data.name or is_ipv4_shaped(data.name):
            verrors.add(f"{schema}.name", "Bucket names may not contain adjacent dots or look like an IPv4 address.")
        filters: list[Any] = [["name", "=", data.name]]
        if old:
            filters.append(["id", "!=", old.id])
        if await self.query(filters, {"select": ["id"]}):
            verrors.add(f"{schema}.name", "A bucket with this name already exists.")

        dataset_layout = data.layout == "DATASET"
        if dataset_layout:
            if data.versioning != "OFF":
                verrors.add(
                    f"{schema}.versioning", "A DATASET bucket is read-only and does not support versioning."
                )
            if data.object_lock:
                verrors.add(f"{schema}.object_lock", "Object lock is not supported on a DATASET bucket.")
            if data.snapshot_versions:
                verrors.add(
                    f"{schema}.snapshot_versions", "Snapshot versions are not supported on a DATASET bucket."
                )

        # only turning versioning on needs the license
        if data.versioning != "OFF" and not dataset_layout and (old is None or old.versioning == "OFF"):
            entitlement = await self.call2(self.s.truenas.entitlements.check, LicenseFeature.S3_VERSIONING)
            if not entitlement.entitled:
                verrors.add(f"{schema}.versioning", entitlement.message)

        if old:
            if old.object_lock and not data.object_lock:
                verrors.add(f"{schema}.object_lock", "Object lock cannot be disabled once enabled.")
            if old.versioning != "OFF" and data.versioning == "OFF":
                verrors.add(
                    f"{schema}.versioning",
                    "Versioning cannot be returned to OFF once enabled. Suspend it instead: a suspended bucket "
                    "keeps its stored versions. sharing.s3.force_disable_versioning forces it off, destroying "
                    "every prior object version.",
                )

        if data.object_lock:
            if data.versioning != "ENABLED":
                verrors.add(f"{schema}.versioning", "Object lock requires versioning to be ENABLED.")
            if data.permissions_model == "MULTIPROTOCOL":
                verrors.add(
                    f"{schema}.permissions_model",
                    "Object lock requires an S3-only permissions model: another protocol could rewrite a locked "
                    "object.",
                )
        if data.snapshot_versions:
            seen: set[str] = set()
            for i, pattern in enumerate(data.snapshot_versions):
                field = f"{schema}.snapshot_versions.{i}"
                if pattern != pattern.strip() or len(pattern) > 255:
                    verrors.add(field, "A pattern is at most 255 characters with no leading or trailing whitespace.")
                elif not set(pattern) <= SNAPSHOT_PATTERN_CHARS:
                    verrors.add(field, "A pattern may contain letters, digits, `-`, `_`, `.`, `:`, space, `*` and `?`.")
                elif pattern in seen:
                    verrors.add(field, "This pattern is listed twice.")
                seen.add(pattern)

        if data.object_lock_default_mode is not None or data.object_lock_default_days is not None:
            if not data.object_lock:
                verrors.add(f"{schema}.object_lock", "A default retention rule requires object lock to be enabled.")
            if data.object_lock_default_mode is None:
                verrors.add(f"{schema}.object_lock_default_mode", "A default retention rule needs a mode.")
            if data.object_lock_default_days is None:
                verrors.add(f"{schema}.object_lock_default_days", "A default retention rule needs a period.")

        if data.audit is not None or data.audit_overflow is not None:
            entitlement = await self.call2(self.s.truenas.entitlements.check, LicenseFeature.S3_AUDIT)
            if not entitlement.entitled:
                verrors.add(f"{schema}.audit", entitlement.message)

        await validate_grants(self.middleware, f"{schema}.grants", data.grants, verrors)

    @private
    async def bucket_of_path(
        self, path: str, dataset: str | None = None, relative_path: str | None = None
    ) -> BucketPath | None:
        """Internal check for whether a given path is inside a BUCKET layout S3 share."""
        real = path if dataset is not None else await self.middleware.run_in_thread(os.path.realpath, path)

        def within(bucket: str) -> str | None:
            """The path within `bucket` that `path` names, or None when it
            is not in it."""
            if dataset is not None:
                if dataset != bucket and not dataset.startswith(f"{bucket}/"):
                    return None
                # a child dataset of the bucket mounts at <bucket>/<its leaf path>
                return "/".join(part for part in (dataset[len(bucket) + 1:], relative_path) if part)
            mountpoint = f"/mnt/{bucket}"
            if real != mountpoint and not real.startswith(f"{mountpoint}/"):
                return None
            return real[len(mountpoint) + 1:]

        rows = await self.middleware.call(
            "datastore.query", self._config.datastore, [], {"select": ["name", "dataset", "layout"]}
        )
        found: BucketPath | None = None
        for row in rows:
            if row["layout"] == "DATASET":
                continue
            rel = within(row["dataset"])
            if rel is not None and (found is None or len(row["dataset"]) > len(found.dataset)):
                found = BucketPath(row["name"], row["dataset"], rel)
        return found

    @private
    async def validate_writable_path(
        self,
        verrors: ValidationErrors,
        field: str,
        path: str,
        dataset: str | None = None,
        relative_path: str | None = None,
    ) -> None:
        """Validation for whether the given path is OK for writes from a non-S3 service."""
        if (bucket := await self.bucket_of_path(path, dataset, relative_path)) is None:
            return
        verrors.add(
            field,
            f"{path} is on the dataset of S3 bucket {bucket.name!r}. Only the S3 service may write to a bucket. "
            f"Bucket contents must be accessed through the /mnt/{bucket.dataset}/{SHARE_ROOT} directory in a "
            "read-only manner.",
        )

    @private
    async def validate_objects_path(
        self,
        verrors: ValidationErrors,
        field: str,
        path: str,
        dataset: str | None = None,
        relative_path: str | None = None,
    ) -> None:
        """Refuse a share path on a BUCKET dataset unless it is the `s3data`
        directory or under it."""
        if (bucket := await self.bucket_of_path(path, dataset, relative_path)) is None:
            return
        if bucket.within != SHARE_ROOT and not bucket.within.startswith(f"{SHARE_ROOT}/"):
            verrors.add(
                field,
                f"{path} exposes private state of S3 bucket {bucket.name!r}. Bucket contents must be accessed "
                f"through the /mnt/{bucket.dataset}/{SHARE_ROOT} directory in a read-only manner.",
            )

    @private
    def normalize_ownership(self, data: EntryT) -> EntryT:
        """Fold `object_ownership` to `OBJECT_WRITER` for a `MULTIPROTOCOL` row, as the S3 service does."""
        model, ownership = data.permissions_model, data.object_ownership
        if model == "MULTIPROTOCOL":
            ownership = "OBJECT_WRITER"
        return data.model_copy(update={"permissions_model": model, "object_ownership": ownership})

    @private
    async def resolve_owner(self, schema: str, username: str, verrors: ValidationErrors) -> int | None:
        """Resolve the owner's uid. Root is refused."""
        try:
            user = await self.middleware.call("user.get_user_obj", {"username": username})
        except KeyError:
            verrors.add(f"{schema}.owner", f"User {username!r} does not exist.")
            return None
        uid: int = user["pw_uid"]
        if uid == 0:
            verrors.add(f"{schema}.owner", "A bucket may not be owned by root.")
            return None
        return uid

    @private
    def compress(self, data: SharingS3Entry, owner_uid: int) -> dict[str, Any]:
        row = data.model_dump(exclude={"id", "locked", "owner", "tier", "create_dataset"})
        row["grants"] = [g.model_dump(exclude={"name"}) for g in data.grants]
        row["owner_uid"] = owner_uid
        if isinstance(row["audit"], list):
            row["audit"] = list(dict.fromkeys(row["audit"]))
        return row

    @private
    async def mountpoint(self, dataset: str) -> str | None:
        rows = await self.call2(
            self.s.zfs.resource.list_impl, ZFSResourceQuery(paths=[dataset], properties=["mountpoint"])
        )
        mountpoint = rows[0]["properties"]["mountpoint"]["value"] if rows else None
        return mountpoint if mountpoint and mountpoint.startswith("/") else None

    @private
    async def owner_of_uid(self, schema: str, uid: int, verrors: ValidationErrors) -> str | None:
        """The account a backed-up owner uid belongs to."""
        try:
            user = await self.middleware.call("user.get_user_obj", {"uid": uid})
        except KeyError:
            verrors.add(
                f"{schema}.dataset",
                f"The config backup on this dataset names uid {uid} as the bucket's owner, which no account "
                f"holds. Create that account, or state owner.",
            )
            return None
        pw_name: str = user["pw_name"]
        return pw_name

    @private
    def config_backup_row(self, entry: SharingS3Entry) -> dict[str, Any]:
        """The datastore row as written to the config backup."""
        return self.compress(entry, entry.owner_uid)

    @private
    async def reconcile_config_backups(self, mounts: dict[str, str]) -> None:
        """Bring every config backup up to date with its database entry."""
        if not mounts:
            return
        try:
            entries: list[SharingS3Entry] = await self.middleware.call("sharing.s3.query")
            # DATASET buckets get no backup
            work = [
                (mounts[entry.dataset], self.config_backup_row(entry))
                for entry in entries
                if entry.dataset in mounts and entry.layout == "BUCKET"
            ]
            failures = await self.middleware.run_in_thread(write_config_backups, work)
        except Exception:
            # a failed backup write never fails the render
            self.logger.warning("s3: failed to reconcile the bucket config backups", exc_info=True)
            return
        for mount, error in failures:
            self.logger.warning("%s: failed to write the bucket config backup: %r", mount, error)

    @private
    async def derive_dataset(self, schema: str, name: str, verrors: ValidationErrors) -> str | None:
        """Pick the dataset for a bucket created without `dataset`:
        `managed_root_dataset/<name>`, with a `_N` suffix if that name is in use.
        An existing dataset is never reused."""
        root = (await self.middleware.call("s3.config")).managed_root_dataset
        if not root:
            verrors.add(
                f"{schema}.dataset",
                "This bucket named no dataset, and the S3 service has no managed_root_dataset to put one under.",
            )
            return None
        try:
            rows = await self.call2(
                self.s.zfs.resource.list_impl,
                ZFSResourceQuery(paths=[root], properties=None, max_depth=1),
            )
        except ZFSPathNotFoundException:
            rows = []
        if not rows:
            # the managed root was removed after s3.update checked it
            verrors.add(
                f"{schema}.dataset",
                f"The S3 service's managed_root_dataset {root!r} does not exist.",
                errno.ENOENT,
            )
            return None
        taken = {row["name"] for row in rows}
        # a bucket row keeps its dataset name after the dataset is gone, and the column is unique
        taken |= {
            row["dataset"]
            for row in await self.middleware.call(
                "datastore.query", self._config.datastore, [], {"select": ["dataset"]}
            )
        }
        for suffix in range(MANAGED_NAME_MAX_SUFFIX + 1):
            leaf = name if suffix == 0 else f"{name}_{suffix}"
            candidate = f"{root}/{leaf}"
            if candidate not in taken:
                return candidate
        verrors.add(
            f"{schema}.dataset",
            f"{root!r} already holds a dataset named {name!r} and every suffix to "
            f"_{MANAGED_NAME_MAX_SUFFIX}. Remove an unused dataset, or give a dataset value.",
            errno.EEXIST,
        )
        return None

    @private
    async def create_dataset(self, schema: str, name: str) -> None:
        """Create the bucket's dataset with the properties the S3 service requires."""
        verrors = ValidationErrors()
        try:
            await self.call2(
                self.s.zfs.resource.create_impl,
                ZFSResourceCreateArgsData(path=name, properties=bucket_dataset_properties()),
            )
        except ZFSPathAlreadyExistsException as e:
            # an existing dataset is used only with create_dataset false
            verrors.add(f"{schema}.dataset", e.message, errno.EEXIST)
        except ZFSPathNotFoundException as e:
            verrors.add(f"{schema}.dataset", e.message, errno.ENOENT)
        except ValidationError as e:
            verrors.add(f"{schema}.dataset", e.errmsg, e.errno)
        except ValueError as e:
            verrors.add(f"{schema}.dataset", str(e), errno.EINVAL)
        verrors.check()
        if await self.mountpoint(name) is None:
            await self.destroy_dataset(name)
            raise CallError(f"{name}: the new dataset has no usable mount point.")

    @private
    async def destroy_dataset(self, name: str) -> None:
        try:
            await self.call2(self.s.zfs.resource.destroy_impl, name)
        except ZFSDestroyFailedException as e:
            self.logger.warning("%s: failed to remove the bucket dataset: %s", name, e.message)

    @private
    async def validate_existing_dataset(
        self, schema: str, dataset: str, layout: S3BucketLayout, verrors: ValidationErrors
    ) -> None:
        """Refuse an existing dataset the S3 service would refuse at
        registration. A `BUCKET` bucket also requires it empty."""
        field = f"{schema}.dataset"
        if has_internal_path(dataset):
            verrors.add(field, f"{dataset!r} is a system dataset.")
            return
        try:
            rows = await self.call2(
                self.s.zfs.resource.list_impl,
                ZFSResourceQuery(paths=[dataset], properties=[*RECOVER_PROPERTIES, "keystatus"]),
            )
        except ZFSPathNotFoundException:
            rows = []
        if not rows:
            verrors.add(field, f"{dataset!r} does not exist.", errno.ENOENT)
            return
        if rows[0]["type"] != "FILESYSTEM":
            verrors.add(field, f"{dataset!r} is a volume, not a dataset.")
            return
        properties = rows[0]["properties"]
        if properties["mounted"]["raw"] != "yes":
            # a locked dataset is never mounted
            if properties["keystatus"]["raw"] == "unavailable":
                verrors.add(field, f"{dataset!r} is locked.")
            else:
                verrors.add(field, f"{dataset!r} is not mounted.")
            return
        mount = properties["mountpoint"]["raw"]
        if mount != f"/mnt/{dataset}":
            verrors.add(field, f"{dataset!r} is mounted at {mount}, not at /mnt/{dataset}.")
            return
        await check_path_resides_within_volume(verrors, self.middleware, field, mount)
        try:
            markers = await self.middleware.run_in_thread(bucket_layout_markers, mount)
        except OSError as e:
            verrors.add(field, f"{mount}: {e.strerror}", e.errno or errno.EIO)
            return
        if markers:
            verrors.add(
                field,
                f"{dataset!r} already holds an S3 bucket ({', '.join(markers)}). Use sharing.s3.recover to "
                "register it as a bucket.",
            )
            return
        if layout == "DATASET":
            if properties["xattr"]["raw"] == "off":
                verrors.add(
                    field, f"{dataset!r} has xattr=off. The S3 service reads extended attributes on every object."
                )
            return
        for blocker in recovery_blockers(properties, []):
            verrors.add(field, blocker)
        # the size of a ZFS directory is its entry count, 2 when empty
        if (await self.middleware.run_in_thread(os.stat, mount)).st_size > 2:
            verrors.add(field, f"{dataset!r} is not empty. A BUCKET bucket requires an empty dataset.")

    @api_method(
        SharingS3CreateArgs,
        SharingS3CreateResult,
        audit="S3 bucket create",
        audit_extended=lambda data: data["name"],
        check_annotations=True,
    )
    async def do_create(self, data: SharingS3Create) -> SharingS3Entry:
        """
        Create an S3 bucket.

        With ``create_dataset`` true, the dataset is created with the properties
        the S3 service requires and must not exist beforehand. If ``dataset`` is
        omitted, it is created under the S3 service's ``managed_root_dataset``
        with the name of the bucket, plus a ``_N`` suffix if that name is in use.
        Buckets created through the S3 protocol always use that default.

        With ``create_dataset`` false, ``dataset`` must be an existing mounted
        dataset that is not a system dataset, is not used by another bucket and
        does not already hold an S3 bucket. A ``BUCKET`` bucket also requires it
        to be empty, with the properties a created dataset gets. Use
        :method:`sharing.s3.recover` for a dataset that already holds a bucket.

        With the ``DATASET`` layout, ``create_dataset`` defaults to false and
        cannot be true. ``permissions_model`` defaults to ``MULTIPROTOCOL``.
        ``versioning``, ``object_lock`` and ``snapshot_versions`` are not
        supported.
        """
        async with BUCKET_LOCK:
            verrors = ValidationErrors()
            if data.layout == "DATASET":
                defaults = {"permissions_model": "MULTIPROTOCOL", "create_dataset": False}
                data = data.model_copy(update={k: v for k, v in defaults.items() if k not in data.model_fields_set})
                if data.create_dataset:
                    verrors.add("sharing_s3_create.create_dataset", "A DATASET bucket uses an existing dataset.")
            data = self.normalize_ownership(data)
            await self.validate(data, "sharing_s3_create", verrors)
            owner_uid = await self.resolve_owner("sharing_s3_create", data.owner, verrors)
            if data.dataset is None:
                if data.create_dataset:
                    data.dataset = await self.derive_dataset("sharing_s3_create", data.name, verrors)
                else:
                    verrors.add("sharing_s3_create.dataset", "`dataset` is required when `create_dataset` is false.")
            elif await self.query([["dataset", "=", data.dataset]], {"select": ["id"]}):
                verrors.add("sharing_s3_create.dataset", "Another bucket already uses this dataset.")
            elif not data.create_dataset:
                await self.validate_existing_dataset("sharing_s3_create", data.dataset, data.layout, verrors)
            verrors.check()
            assert owner_uid is not None
            assert data.dataset is not None

            # on failure, destroy only a dataset that this method created
            created_dataset = data.create_dataset
            if created_dataset:
                await self.create_dataset("sharing_s3_create", data.dataset)
            id_: int | None = None
            try:
                id_ = await self.middleware.call(
                    "datastore.insert", self._config.datastore, self.compress(data, owner_uid)
                )
                await render_and_apply(self.middleware)
            except Exception:
                # remove the row first, then the dataset it owned
                if id_ is not None:
                    try:
                        await self.middleware.call("datastore.delete", self._config.datastore, id_)
                    except Exception:
                        self.logger.warning(
                            "%s: failed to remove the bucket row after a failed create", data.name, exc_info=True
                        )
                    else:
                        if created_dataset:
                            await self.destroy_dataset(data.dataset)
                elif created_dataset:
                    await self.destroy_dataset(data.dataset)
                raise
            return await self.get_instance(id_)

    @api_method(
        SharingS3UpdateArgs,
        SharingS3UpdateResult,
        audit="S3 bucket update",
        audit_callback=True,
        check_annotations=True,
    )
    async def do_update(self, audit_callback: AuditCallback, id_: int, data: SharingS3Update) -> SharingS3Entry:
        """
        Update S3 bucket ``id``.

        ``grants`` replaces the whole grant list. The dataset and the layout
        cannot be changed. Object lock cannot be disabled once enabled.
        Versioning cannot return to ``OFF`` except through
        :method:`sharing.s3.force_disable_versioning`. Changing
        ``permissions_model`` from ``MULTIPROTOCOL`` requires ``object_ownership``
        in the same call.

        Enabling or disabling the bucket and changing the owner, the grants or
        the audit settings reload the S3 service. Changing the permissions model,
        the object ownership, the ETag mode, the snapshot selection or object-lock
        enablement restarts it.
        """
        async with BUCKET_LOCK:
            old = await self.get_instance(id_)
            audit_callback(old.name)

            new = old.updated(data)
            given = data.model_dump(exclude_unset=True)
            verrors = ValidationErrors()
            new = self.normalize_ownership(new)
            # leaving MULTIPROTOCOL must state the ownership: the stored value is the OBJECT_WRITER fold
            if (
                old.permissions_model == "MULTIPROTOCOL"
                and new.permissions_model != "MULTIPROTOCOL"
                and "object_ownership" not in given
            ):
                verrors.add(
                    "sharing_s3_update.object_ownership",
                    "State object_ownership when moving permissions_model off MULTIPROTOCOL. The stored value on a "
                    "MULTIPROTOCOL bucket is its OBJECT_WRITER fold, which would otherwise take effect and enable "
                    "S3 ACLs.",
                )
            await self.validate(new, "sharing_s3_update", verrors, old)
            # owners are compared by uid
            owner_uid = old.owner_uid
            if "owner" in given:
                resolved = await self.resolve_owner("sharing_s3_update", new.owner, verrors)
                if resolved is not None:
                    owner_uid = resolved
            verrors.check()

            # a new owner is not applied to the s3data directory
            await self.middleware.call("datastore.update", self._config.datastore, id_, self.compress(new, owner_uid))
            await render_and_apply(self.middleware)
            return await self.get_instance(id_)

    @api_method(
        SharingS3DeleteArgs,
        SharingS3DeleteResult,
        audit="S3 bucket delete",
        audit_callback=True,
        check_annotations=True,
    )
    async def do_delete(self, audit_callback: AuditCallback, id_: int) -> Literal[True]:
        """
        Deregister S3 bucket ``id``.

        The bucket's dataset and every object in it are left in place,
        retained objects included. The S3 service stops serving them. Reloads
        the S3 service.
        """
        async with BUCKET_LOCK:
            bucket = await self.get_instance(id_)
            audit_callback(bucket.name)
            await self.middleware.call("datastore.delete", self._config.datastore, id_)
            await self.call2(self.s.alert.oneshot_delete, MISSING_ALERT, id_)
            await render_and_apply(self.middleware)
            return True

    @api_method(
        SharingS3ForceDisableVersioningArgs,
        SharingS3ForceDisableVersioningResult,
        audit="S3 bucket force disable versioning",
        audit_callback=True,
        roles=["SHARING_S3_WRITE"],
        check_annotations=True,
    )
    async def force_disable_versioning(self, audit_callback: AuditCallback, id_: int) -> SharingS3Entry:
        """
        Force versioning off for S3 bucket ``id``, destroying its version history.

        :method:`sharing.s3.update` refuses to turn versioning off once it has
        been enabled or suspended. This method sets ``versioning`` to ``OFF``,
        clears ``snapshot_versions`` and restarts the S3 service. A bucket with
        object lock enabled is refused.

        .. warning:: This operation is destructive and irreversible. Every prior
           version of every object and every delete marker is lost. The S3 service
           removes the stored version files in the background, so space is
           reclaimed gradually. ZFS snapshots of the dataset still hold the old
           versions until they are destroyed. Enabling versioning again starts
           new history and does not restore what was destroyed.
        """
        async with BUCKET_LOCK:
            bucket = await self.get_instance(id_)
            audit_callback(bucket.name)
            # a root carrying the latch is a locked bucket whatever the row says
            locked = bucket.object_lock
            if not locked and (mount := await self.mountpoint(bucket.dataset)) is not None:
                locked = await self.middleware.run_in_thread(has_latch, mount)
            if locked:
                raise ValidationError(
                    "sharing_s3_force_disable_versioning.id",
                    "Versioning cannot be disabled on a bucket with object lock enabled: a locked bucket keeps its "
                    "version history for as long as it exists.",
                    errno.EPERM,
                )

            changed = bucket.versioning != "OFF" or bool(bucket.snapshot_versions)
            if changed:
                new = bucket.model_copy(update={"versioning": "OFF", "snapshot_versions": []})
                await self.middleware.call(
                    "datastore.update", self._config.datastore, id_, self.compress(new, bucket.owner_uid)
                )
            # rendered even when the row did not move, so a failed apply can be retried
            await render_and_apply(self.middleware)
            entry = await self.get_instance(id_)
            if changed:
                # emit CHANGED like the CRUD wrapper does
                self.middleware.send_event("sharing.s3.query", "CHANGED", id=id_, fields=entry.model_dump())
            return entry

    @api_method(
        SharingS3RecoverArgs,
        SharingS3RecoverResult,
        audit="S3 bucket recover",
        audit_extended=lambda buckets: ", ".join(b["dataset"] for b in buckets),
        roles=["SHARING_S3_WRITE"],
        check_annotations=True,
    )
    async def recover(self, buckets: list[SharingS3RecoverBucket]) -> list[SharingS3RecoveredBucket]:
        """
        Recover buckets from datasets that already hold their objects.

        :method:`sharing.s3.delete` leaves the dataset and its objects in place.
        This method registers such a dataset again from the configuration backup
        middleware keeps in ``.truenas_s3/config_backup.json``.
        :method:`sharing.s3.recoverable_buckets` lists what can be recovered. A
        dataset with no backup is refused. A ``DATASET`` bucket has no backup.
        Create it again instead.

        ``name_override`` and ``owner_override`` replace the stored name and
        owner. Change anything else with :method:`sharing.s3.update` after
        recovering.

        Each dataset gets its own result, in the order requested. A dataset that
        cannot be recovered does not stop the others. The S3 service is reloaded
        once at the end.

        .. warning:: A recovered bucket keeps its grants and any stored S3 ACLs,
           which may now name reused uids.
        """
        async with BUCKET_LOCK:
            # names and datasets claimed earlier in this call are not in the registry yet
            claimed_names: set[str] = set()
            claimed_datasets: set[str] = set()
            rows: list[dict[str, Any] | None] = []
            failures: list[str | None] = []
            for i, wanted in enumerate(buckets):
                verrors = ValidationErrors()
                rows.append(
                    await self.recovered_row(
                        f"sharing_s3_recover.buckets.{i}", wanted, claimed_names, claimed_datasets, verrors
                    )
                )
                # one reason per dataset, so several read as one sentence
                failures.append(" ".join(error.errmsg for error in verrors.errors) or None)

            ids: list[int | None] = []
            for i, row in enumerate(rows):
                if row is None:
                    ids.append(None)
                    continue
                try:
                    ids.append(await self.middleware.call("datastore.insert", self._config.datastore, row))
                except Exception as e:
                    self.logger.warning("%s: failed to insert the recovered bucket row", row["dataset"], exc_info=True)
                    ids.append(None)
                    failures[i] = str(e)

            if any(id_ is not None for id_ in ids):
                # nothing is unwound: what was inserted stays
                await render_and_apply(self.middleware)

            recovered = []
            for wanted, id_, failure in zip(buckets, ids, failures):
                entry = None
                if id_ is not None:
                    entry = await self.get_instance(id_)
                    # emit ADDED like the CRUD wrapper does
                    self.middleware.send_event("sharing.s3.query", "ADDED", id=id_, fields=entry.model_dump())
                recovered.append(SharingS3RecoveredBucket(dataset=wanted.dataset, bucket=entry, error=failure))
            return recovered

    @private
    async def recovered_row(
        self,
        schema: str,
        wanted: SharingS3RecoverBucket,
        claimed_names: set[str],
        claimed_datasets: set[str],
        verrors: ValidationErrors,
    ) -> dict[str, Any] | None:
        """The datastore row for one dataset, or None with the errors on `verrors`."""
        dataset = wanted.dataset
        if dataset in claimed_datasets:
            verrors.add(f"{schema}.dataset", "This dataset is named twice in the same recovery.")
            return None
        claimed_datasets.add(dataset)
        if await self.query([["dataset", "=", dataset]], {"select": ["id"]}):
            verrors.add(f"{schema}.dataset", "Another bucket already uses this dataset.")
            return None
        try:
            zfs_rows = await self.call2(
                self.s.zfs.resource.list_impl,
                ZFSResourceQuery(paths=[dataset], properties=list(RECOVER_PROPERTIES), get_children=True),
            )
        except ZFSPathNotFoundException as e:
            verrors.add(f"{schema}.dataset", e.message, errno.ENOENT)
            return None
        itself = filter_list(zfs_rows, [*MOUNTED_FILESYSTEM, ["name", "=", dataset]])
        if not itself:
            verrors.add(
                f"{schema}.dataset",
                f"{dataset!r} is not a mounted ZFS filesystem, so what it holds cannot be read.",
            )
            return None
        properties = itself[0]["properties"]
        mount = properties["mountpoint"]["raw"]

        try:
            backup = await self.middleware.run_in_thread(read_config_backup, mount)
        except OSError as e:
            verrors.add(f"{schema}.dataset", f"{SIDE_TREE}/{CONFIG_BACKUP}: {e.strerror}", e.errno or errno.EIO)
            return None
        if backup is None:
            verrors.add(
                f"{schema}.dataset",
                f"{dataset!r} holds no bucket config backup, which is the whole of what a bucket is recovered "
                f"from. Either it never held a bucket, or it held one this version did not back up.",
                errno.ENOENT,
            )
            return None

        beneath = [
            row["name"] for row in filter_list(zfs_rows, [*MOUNTED_FILESYSTEM, ["name", "^", f"{dataset}/"]])
        ]
        for blocker in recovery_blockers(properties, beneath):
            verrors.add(f"{schema}.dataset", blocker)

        new = await self.row_from_backup(schema, dataset, backup, wanted, verrors)
        if new is None:
            return None
        new = self.normalize_ownership(new)
        await self.validate(new, schema, verrors)
        if new.name in claimed_names:
            verrors.add(f"{schema}.name", "Another bucket in the same recovery takes this name.")
        claimed_names.add(new.name)
        owner_uid = await self.resolve_owner(schema, new.owner, verrors)
        self.check_against_dataset(schema, new, properties, verrors)
        if verrors or owner_uid is None:
            return None
        return self.compress(new, owner_uid)

    @private
    async def row_from_backup(
        self,
        schema: str,
        dataset: str,
        backup: dict[str, Any],
        wanted: SharingS3RecoverBucket,
        verrors: ValidationErrors,
    ) -> SharingS3Create | None:
        """The row to insert: the backup under the stated name and owner."""
        # fields this method supplies itself, not the backup. Only BUCKET
        # buckets write a backup, so a recovered row is always BUCKET.
        supplied = ("dataset", "layout", "owner", "owner_uid", "version_number")

        owner = wanted.owner_override
        if owner is None:
            uid = backup.get("owner_uid")
            if not isinstance(uid, int):
                verrors.add(
                    f"{schema}.dataset",
                    f"The bucket config backup on {dataset!r} names no owner, and none was stated.",
                )
                return None
            owner = await self.owner_of_uid(schema, uid, verrors)
            if owner is None:
                return None
        row = {k: v for k, v in backup.items() if k not in supplied}
        if wanted.name_override is not None:
            row["name"] = wanted.name_override
        try:
            return SharingS3Create(**row, dataset=dataset, owner=owner)
        except ValueError as e:
            verrors.add(
                f"{schema}.dataset",
                f"The bucket config backup on {dataset!r} is not a row this version can read: {e}",
            )
            return None

    @private
    def check_against_dataset(
        self,
        schema: str,
        new: SharingS3Create,
        properties: dict[str, Any],
        verrors: ValidationErrors,
    ) -> None:
        """Refuse a dataset whose properties cannot serve the row."""
        if new.snapshot_versions and (properties.get("snapdir") or {}).get("raw") == "disabled":
            verrors.add(
                f"{schema}.dataset",
                "This dataset has snapdir disabled, so the .zfs/snapshot directory the backed-up snapshot "
                "selection is served through does not open.",
            )

    @api_method(
        SharingS3RecoverableBucketsArgs,
        SharingS3RecoverableBucketsResult,
        roles=["SHARING_S3_READ"],
        check_annotations=True,
    )
    async def recoverable_buckets(self) -> list[SharingS3RecoverableBucket]:
        """
        Returns buckets that are no longer registered but whose datasets still
        exist.

        Every mounted dataset no bucket uses is scanned for a configuration
        backup, and the configuration each backup holds is returned.
        :method:`sharing.s3.recover` registers exactly that. Unmounted datasets
        and backups this version cannot read are skipped. A ``DATASET`` bucket
        has no backup and is never listed.
        """
        used = {
            row["dataset"]
            for row in await self.middleware.call(
                "datastore.query", self._config.datastore, [], {"select": ["dataset"]}
            )
        }
        rows = await self.call2(
            self.s.zfs.resource.list_impl,
            ZFSResourceQuery(paths=[], properties=["mountpoint", "mounted"], get_children=True),
        )
        mounts = {
            row["name"]: row["properties"]["mountpoint"]["raw"]
            for row in filter_list(rows, [*MOUNTED_FILESYSTEM, ["name", "nin", list(used)]])
        }
        found = await self.middleware.run_in_thread(read_config_backups, mounts)

        # per row, so one unreadable backup does not fail the listing
        buckets = []
        for row in found:
            try:
                names = await self.bucket_extend_context([row], {})
                buckets.append(SharingS3RecoverableBucket(**await self.bucket_extend(row, names)))
            except Exception:
                self.logger.warning(
                    "%s: the bucket config backup is not a row this version can read", row["dataset"], exc_info=True
                )
        return buckets

    @api_method(SharingS3AuditChoicesArgs, SharingS3AuditChoicesResult, check_annotations=True)
    async def audit_choices(self) -> dict[str, str]:
        """
        Returns the actions an audit mask may name.
        """
        return {action: action for action in AUDIT_ACTIONS}

    @private
    async def audited_bucket_names(self) -> list[str]:
        """Enabled buckets whose effective audit mask is not empty, for
        `audit.config`."""
        if not (await self.call2(self.s.truenas.entitlements.check, LicenseFeature.S3_AUDIT)).entitled:
            return []
        config: S3Entry = await self.middleware.call("s3.config")
        buckets: list[SharingS3Entry] = await self.middleware.call("sharing.s3.query", [["enabled", "=", True]])
        names = []
        for bucket in buckets:
            mask = bucket.audit if bucket.audit is not None else config.default_audit
            if mask:
                names.append(bucket.name)
        return names


class S3FSAttachmentDelegate(LockableFSAttachmentDelegate[SharingS3Entry]):
    name = "s3"
    title = "S3 Bucket"
    service = "s3"
    service_class = SharingS3Service

    async def remove_alert(self, attachment: SharingS3Entry) -> None:
        # a bucket deleted or toggled with its dataset is not missing it
        await super().remove_alert(attachment)
        await self.middleware.call("alert.oneshot_delete", MISSING_ALERT, attachment.id)

    async def restart_reload_services(self, attachments: list[SharingS3Entry]) -> None:
        # the daemon pins a registered dataset's mount, so the restart must land before the ZFS operation
        await render_and_apply(self.middleware, force_restart=True)


async def setup(middleware: Middleware) -> None:
    await middleware.call2(
        middleware.services.zfs.resource.register_attachment_delegate,
        S3FSAttachmentDelegate(middleware),
    )
