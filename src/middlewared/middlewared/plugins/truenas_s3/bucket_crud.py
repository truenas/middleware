"""Buckets: the S3 service's share-like entity.

A bucket is a ZFS dataset this plugin creates and registers with the
daemon. The daemon pins a registered dataset's mount. Creating,
dropping, enabling or disabling a bucket and changing the owner, the
grants or the audit mask apply to a running service on a reload;
changing a field consumed at registration (the dataset, the models,
the ETag mode) requires a restart. The daemon reports which applies
per change, and middleware acts on that (lifecycle.py). The grants
live on the bucket, so they can never outlive it.
"""

from __future__ import annotations

import errno
import ipaddress
import os
import string
import typing
from typing import Any, Literal, TypeVar, TYPE_CHECKING

from truenas_pylicensed.features import LicenseFeature

from middlewared.api import api_method
from middlewared.api.current import (
    S3AuditAction,
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
    SharingS3Update,
    SharingS3UpdateArgs,
    SharingS3UpdateResult,
    ZFSResourceCreateArgsData,
    ZFSResourceCreateProperties,
    ZFSResourceQuery,
)
from middlewared.common.attachment import LockableFSAttachmentDelegate
from middlewared.plugins.zfs.exceptions import ZFSPathAlreadyExistsException, ZFSPathNotFoundException
from middlewared.service import CallError, SharingService, ValidationError, ValidationErrors, private
import middlewared.sqlalchemy as sa
from middlewared.utils.path import FSLocation
from middlewared.utils.types import AuditCallback

from .grants import PrincipalNames, Principals, grant_principals, label_grants, principal_names, validate_grants
from .lifecycle import MISSING_ALERT, render_and_apply

if TYPE_CHECKING:
    from middlewared.main import Middleware

__all__ = ("SharingS3Service", "S3FSAttachmentDelegate")

AUDIT_ACTIONS: tuple[str, ...] = typing.get_args(S3AuditAction)

# a whole bucket row, whichever of the two shapes the caller sent one in
EntryT = TypeVar("EntryT", bound=SharingS3Entry)

MANAGED_NAME_MAX_SUFFIX = 10
"""Highest `_N` suffix a derived dataset name uses. The names tried under the
managed root are the name of the bucket, then that name with `_1` to `_10`.
The limit stops an endless loop and gives an error the administrator can
read."""

BUCKET_DATASET_PROPERTIES = {
    # what the S3 on-disk format requires of a bucket's dataset. The first
    # three are create-time only and would otherwise inherit from the parent;
    # the daemon never re-checks any of them
    "casesensitivity": "sensitive",
    "normalization": "none",
    "utf8only": "off",
    "xattr": "sa",
    # the daemon passes a directory's inheritable NFSv4 ACEs to every object
    # it stages, and a POSIX ACL parent has none to pass. restricted keeps a
    # chmod from another protocol from stripping them
    "acltype": "nfsv4",
    "aclmode": "restricted",
    "aclinherit": "passthrough",
}


class SharingS3Model(sa.Model):
    """No column carries a default: every row is inserted whole from the
    API model, whose defaults are the one place they are stated."""

    __tablename__ = "truenas_s3_bucket"

    id = sa.Column(sa.Integer(), primary_key=True)
    name = sa.Column(sa.String(63), unique=True)
    dataset = sa.Column(sa.String(255), unique=True)
    enabled = sa.Column(sa.Boolean())
    # the uid is the owner; its name is resolved when read, never stored,
    # so a renamed account reads as its new name and a reused name never
    # inherits a bucket
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
    # NULL inherits the service default; an empty list audits nothing, so
    # the column carries no type to turn NULL into an empty value
    audit = sa.Column(sa.JSON(None), nullable=True)  # type: ignore[arg-type]
    audit_overflow = sa.Column(sa.String(16), nullable=True)


# ZFS's snapshot name charset plus the two metacharacters the daemon
# matches with; a comma is outside it, which is what lets the patterns
# render comma separated
SNAPSHOT_PATTERN_CHARS = frozenset(string.ascii_letters + string.digits + "-_.: *?")


def is_ipv4_shaped(name: str) -> bool:
    """Whether the standard parser reads `name` as an IPv4 address. The S3
    service applies the same test (Rust's `std::net::Ipv4Addr`, the same
    grammar), and the two must agree: a name only one side refuses is either
    a rendered row the service refuses whole-file, or an S3 protocol create
    refused for a reason its error cannot carry."""
    try:
        ipaddress.IPv4Address(name)
    except ValueError:
        return False
    return True


def has_latch(mount: str) -> bool:
    """Whether the dataset root carries the S3 service's Object Lock latch.
    Presence is the whole test: the record is the daemon's to decode, and
    the daemon never clears or weakens it, so a root carrying it is a
    locked bucket whatever the row says (`trusted.tns3_latch`,
    ARCHITECTURE.METADATA.md in the truenas_s3 repository)."""
    try:
        os.getxattr(mount, "trusted.tns3_latch")
    except OSError as e:
        if e.errno in (errno.ENODATA, errno.ENOENT, errno.ENOTDIR):
            return False
        raise
    return True


class SharingS3Service(SharingService[SharingS3Entry]):
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
        # the bucket is its dataset, mounted where every dataset middleware
        # makes is: what the share machinery asks a path for (the locked
        # check, the dataset attachment delegate) is answered from the
        # dataset name rather than stored beside it
        dataset = data["dataset"] if isinstance(data, dict) else data.dataset
        return f"/mnt/{dataset}"

    @private
    async def bucket_extend_context(self, rows: list[dict[str, Any]], extra: dict[str, Any]) -> PrincipalNames:
        """Every owner and grant principal across the rows, resolved once
        each rather than once per row."""
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

        # Turning versioning on needs the license. A bucket that already has it
        # keeps it, since the one way rule below never lets it return to OFF.
        if data.versioning != "OFF" and (old is None or old.versioning == "OFF"):
            entitlement = await self.call2(self.s.truenas.entitlements.check, LicenseFeature.S3_VERSIONING)
            if not entitlement.entitled:
                verrors.add(f"{schema}.versioning", entitlement.message)

        # Two one-way fields. Object lock enablement is latched on the dataset
        # root and never lowers: the S3 service refuses to serve a bucket whose
        # row contradicts the latch, so turning it off here would only take the
        # bucket out of service. Versioning has no way back to OFF — the
        # on-disk format's own rule: stored versions would go unreachable, and
        # a delete would unlink the live object where a versioned bucket mints
        # a delete marker. force_disable_versioning is the one deliberate
        # exception, and destroying the stored versions is its contract.
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
    def normalize_ownership(self, data: EntryT) -> EntryT:
        """The pair a row is stored as.

        `permissions_model` and `object_ownership` are one axis each:
        the first says how the S3 service treats the filesystem
        permissions on the tree, the second which account an S3
        operation runs as and whether the bucket supports S3 ACLs.
        Neither is always stored as it was given.

        A `MULTIPROTOCOL` row folds to `OBJECT_WRITER` whatever it was
        given, as the S3 service does with it: the other protocols'
        users own the filesystem permissions, so the caller's own uid is
        the only one that may act, and such a row supports no S3 ACLs
        under any value. Folded rather than refused, so that a shared
        bucket may be created without restating the default, and stored
        folded so the row reads back as the service runs it.
        """
        model, ownership = data.permissions_model, data.object_ownership
        if model == "MULTIPROTOCOL":
            ownership = "OBJECT_WRITER"
        return data.model_copy(update={"permissions_model": model, "object_ownership": ownership})

    @private
    async def resolve_owner(self, schema: str, username: str, verrors: ValidationErrors) -> int | None:
        """The owner's uid, refusing root.

        The owner bypasses the bucket's grants, owns the `s3data`
        directory the service creates, and owns every object written
        under `BUCKET_OWNER_ENFORCED`. As uid 0 that is an owner the
        filesystem does not restrain either, which leaves the bucket's
        access control stating nothing about what its owner reaches.
        """
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
        row = data.model_dump(exclude={"id", "locked", "owner"})
        row["grants"] = [g.model_dump(exclude={"name"}) for g in data.grants]
        row["owner_uid"] = owner_uid
        # Set semantics with the given order kept: the S3 service refuses a
        # mask that names an action twice, and a real set would render in
        # hash order, churning the file between generates.
        if isinstance(row["audit"], list):
            row["audit"] = list(dict.fromkeys(row["audit"]))
        return row

    @private
    async def mountpoint(self, dataset: str) -> str | None:
        """Where the bucket's dataset is mounted, or None when the dataset
        is gone. Read from ZFS whenever it is needed rather than kept: the
        dataset is the bucket's identity and its mount point follows it."""
        rows = await self.call2(
            self.s.zfs.resource.query_impl, ZFSResourceQuery(paths=[dataset], properties=["mountpoint"])
        )
        mountpoint = rows[0]["properties"]["mountpoint"]["value"] if rows else None
        return mountpoint if mountpoint and mountpoint.startswith("/") else None

    @private
    async def derive_dataset(self, schema: str, name: str, verrors: ValidationErrors) -> str | None:
        """Select the dataset for a bucket that gives no `dataset` value.

        This service decides the location, not the S3 daemon. An S3
        client sends only a bucket name. The parent is the S3 service's
        `managed_root_dataset` and the leaf is the name of the bucket.

        If the leaf is in use, add a `_N` suffix. Do not use the existing
        dataset and do not remove it. `sharing.s3.delete` keeps the
        dataset and its objects. A new bucket with an old name must get a
        new dataset. If it does not, it serves the objects of the old
        bucket.

        The separator is an underscore because a bucket name cannot
        contain one. ZFS also permits `A-Z`, `:` and space, but an
        underscore has no other meaning in a path, a shell or a ZFS user
        property. The suffix is therefore unambiguous: `backups_1` is
        always the second dataset for the bucket `backups`. A hyphen is
        ambiguous, because `backups-1` is also the dataset for a bucket
        named `backups-1`.
        """
        root = (await self.middleware.call("s3.config")).managed_root_dataset
        if not root:
            verrors.add(
                f"{schema}.dataset",
                "This bucket named no dataset, and the S3 service has no managed_root_dataset to put one under.",
            )
            return None
        try:
            rows = await self.call2(
                self.s.zfs.resource.query_impl,
                ZFSResourceQuery(paths=[root], properties=None, max_depth=1),
            )
        except ZFSPathNotFoundException:
            rows = []
        if not rows:
            # `s3.update` refuses a root that does not exist, so the root
            # was removed after that check. Reported here to name the
            # setting. The create below would name the derived dataset
            # and report a missing parent instead.
            verrors.add(
                f"{schema}.dataset",
                f"The S3 service's managed_root_dataset {root!r} does not exist.",
                errno.ENOENT,
            )
            return None
        taken = {row["name"] for row in rows}
        # A bucket row keeps its dataset name even when the dataset is
        # gone. The column is unique, so a derived name that matches one
        # fails the insert instead of giving a validation error.
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
        """Create the bucket's dataset with the properties the S3 on-disk
        format requires. The properties are stated here in full rather than
        inherited from any other layer's defaults; normalization and utf8only
        are internal-only create properties, which is what lets them override
        a parent that would otherwise pass its own values down. The share
        root under it, `s3data`, is the daemon's to create: registration
        makes it on the first start, owned by the bucket's owner, and leaves
        it as found from then on."""
        verrors = ValidationErrors()
        try:
            await self.call2(
                self.s.zfs.resource.create_impl,
                ZFSResourceCreateArgsData(
                    path=name,
                    properties=ZFSResourceCreateProperties(**BUCKET_DATASET_PROPERTIES),
                ),
            )
        except ZFSPathAlreadyExistsException as e:
            # the bucket owns its dataset from birth: that is what guarantees
            # the create-time properties. Adopting an existing one is a
            # separate feature
            verrors.add(f"{schema}.dataset", e.message, errno.EEXIST)
        except ZFSPathNotFoundException as e:
            verrors.add(f"{schema}.dataset", e.message, errno.ENOENT)
        except ValueError as e:
            verrors.add(f"{schema}.dataset", str(e), errno.EINVAL)
        verrors.check()
        if await self.mountpoint(name) is None:
            await self.destroy_dataset(name)
            raise CallError(f"{name}: the new dataset has no usable mount point.")

    @private
    async def destroy_dataset(self, name: str) -> None:
        failed, errnum = await self.call2(self.s.zfs.resource.destroy_impl, name)
        if failed:
            self.logger.warning("%s: failed to remove the bucket dataset: %s", name, failed)

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

        The bucket's dataset is created here, with the properties the S3
        service requires, and must not exist beforehand. If you omit
        ``dataset``, the dataset is created under the S3 service's
        ``managed_root_dataset`` and takes the name of the bucket, with a
        ``_N`` suffix if that name is in use. A bucket created through the S3
        protocol always uses that default. Objects live in its
        ``s3data`` directory, which the S3 service creates on its next start
        owned by ``owner``. Under the ``S3`` permissions model the filesystem
        permissions on that tree are ignored and the bucket's grants decide;
        under ``MULTIPROTOCOL`` they are enforced as well, so a grantee other
        than the owner reaches only what they allow and an ACL is set on the
        directory as for any share. Which account a write is recorded as is
        ``object_ownership``'s answer: the owner under
        ``BUCKET_OWNER_ENFORCED``, which is the default and supports no S3
        ACLs, and the account that put the object under the other two values.
        Grants may be given in the same call. Creating a bucket reloads a
        running S3 service rather than restarting it.
        """
        verrors = ValidationErrors()
        data = self.normalize_ownership(data)
        await self.validate(data, "sharing_s3_create", verrors)
        owner_uid = await self.resolve_owner("sharing_s3_create", data.owner, verrors)
        if data.dataset is None:
            data.dataset = await self.derive_dataset("sharing_s3_create", data.name, verrors)
        elif await self.query([["dataset", "=", data.dataset]], {"select": ["id"]}):
            verrors.add("sharing_s3_create.dataset", "Another bucket already uses this dataset.")
        verrors.check()
        assert owner_uid is not None
        assert data.dataset is not None

        await self.create_dataset("sharing_s3_create", data.dataset)
        id_: int | None = None
        try:
            id_ = await self.middleware.call("datastore.insert", self._config.datastore, self.compress(data, owner_uid))
            await render_and_apply(self.middleware)
        except Exception:
            # Unwind to "no bucket": the row goes first, and the dataset only
            # with it — a row that cannot be removed keeps its dataset, which
            # is a consistent bucket, rather than a registered name with no
            # storage behind it.
            if id_ is not None:
                try:
                    await self.middleware.call("datastore.delete", self._config.datastore, id_)
                except Exception:
                    self.logger.warning(
                        "%s: failed to remove the bucket row after a failed create", data.name, exc_info=True
                    )
                else:
                    await self.destroy_dataset(data.dataset)
            else:
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

        ``grants`` replaces the bucket's whole grant list. Enabling or
        disabling the bucket and changing the owner, the grants or the audit
        settings apply to a running S3 service on a reload; changing the
        permissions model, the object ownership, the ETag mode, the snapshot
        selection or object-lock enablement restarts it. The dataset cannot
        be changed, and two fields move one way: object lock cannot be
        disabled once enabled, and versioning cannot return to ``OFF``
        (:method:`sharing.s3.force_disable_versioning` is the destructive
        exception). Moving ``permissions_model`` off ``MULTIPROTOCOL`` requires
        ``object_ownership`` to be stated in the same call: the stored
        value on such a bucket is its ``OBJECT_WRITER`` fold, which would
        otherwise take effect and enable S3 ACLs.
        """
        old = await self.get_instance(id_)
        audit_callback(old.name)

        new = old.updated(data)
        given = data.model_dump(exclude_unset=True)
        verrors = ValidationErrors()
        new = self.normalize_ownership(new)
        # Leaving MULTIPROTOCOL must name the ownership. The stored value
        # on such a row is its OBJECT_WRITER fold, so a merge that kept it
        # would land the flip on the loosest model — live S3 ACLs,
        # writer-owned objects — when the bucket's creator never chose it.
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
        # an owner given by name is compared by the uid it resolves to: a
        # renamed account is the same owner, a deleted and recreated one
        # under the old name is not
        owner_uid = old.owner_uid
        if "owner" in given:
            resolved = await self.resolve_owner("sharing_s3_update", new.owner, verrors)
            if resolved is not None:
                owner_uid = resolved
        verrors.check()

        # a new owner takes the grants, not the directory: the share root is
        # the deployment's once it exists, as it would be under any share
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

        The bucket's dataset and every object in it are left in place, retained
        objects included; the S3 service simply stops serving them. Restarts
        the S3 service.
        """
        bucket = await self.get_instance(id_)
        audit_callback(bucket.name)
        await self.middleware.call("datastore.delete", self._config.datastore, id_)
        await self.middleware.call("alert.oneshot_delete", MISSING_ALERT, id_)
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
        Force versioning off for S3 bucket ``id``, destroying its version
        history.

        :method:`sharing.s3.update` refuses to turn versioning off once it has
        been enabled or suspended, because the version history the bucket has
        accumulated cannot survive it. This method is the deliberate
        exception, for a bucket whose history is no longer wanted: it sets
        ``versioning`` to ``OFF``, clears ``snapshot_versions``, and restarts
        the S3 service — the one versioning change that applies only by a
        restart, so expect the brief interruption; a stopped service applies
        it at its next start. A bucket with object lock enabled is refused: a
        locked bucket keeps its version history for as long as it exists.

        .. warning::

            This operation is destructive and irreversible. Every prior
            version of every object, and every delete marker, is permanently
            lost. Version history stops being served the moment the change
            applies, and the S3 service then slowly removes the previously
            written version files in the background, so the space they occupy
            is reclaimed gradually. ZFS snapshots of the bucket's dataset
            still hold the old versions until those snapshots are destroyed.

        Versioning may be enabled again later. That begins new history and
        does not restore what this method destroyed, though old versions the
        background cleanup has not yet removed reappear in the bucket's
        history until it finishes.
        """
        bucket = await self.get_instance(id_)
        audit_callback(bucket.name)
        # the row, then the latch: the daemon never clears the latch, so a
        # root carrying one is a locked bucket even under a row that
        # (historically) stopped saying so
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
        # rendered and applied even when the row did not move, so a call that
        # failed between the row write and the apply can be retried
        await render_and_apply(self.middleware)
        entry = await self.get_instance(id_)
        if changed:
            # the CRUD wrapper emits CHANGED for create/update/delete; a
            # custom row mutation owes sharing.s3.query subscribers the same
            self.middleware.send_event("sharing.s3.query", "CHANGED", id=id_, fields=entry.model_dump())
        return entry

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

    async def remove_alert(self, attachment: SharingS3Entry | dict[str, Any]) -> None:
        # the missing-dataset alert is keyed by bucket id like the locked
        # one, and a bucket that is deleted or toggled with its dataset is
        # not missing it; a render raises it again if it still is
        await super().remove_alert(attachment)  # type: ignore[no-untyped-call]
        id_ = attachment["id"] if isinstance(attachment, dict) else attachment.id
        await self.middleware.call("alert.oneshot_delete", MISSING_ALERT, id_)

    async def restart_reload_services(self, attachments: list[SharingS3Entry]) -> None:
        # every path here is a registry change: a bucket disabled for an
        # export or lock, re-enabled on import or unlock, or deleted with
        # its dataset. The daemon pins a registered dataset's mount, so the
        # restart has to land before the ZFS operation that follows
        await render_and_apply(self.middleware, force_restart=True)


async def setup(middleware: Middleware) -> None:
    await middleware.call(
        "pool.dataset.register_attachment_delegate",
        S3FSAttachmentDelegate(middleware),  # type: ignore[no-untyped-call]
    )
