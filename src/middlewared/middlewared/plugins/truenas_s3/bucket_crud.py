"""Buckets: the S3 service's share-like entity.

A bucket is a ZFS dataset this plugin creates and registers with the
daemon. The daemon pins a registered dataset's mount and consumes the
registry once at startup, so creating, dropping, enabling or disabling
a bucket restarts the service; the owner, the grants and the audit mask
move on a reload. The grants live on the bucket, so they can never
outlive it.
"""

from __future__ import annotations

import errno
import ipaddress
import string
import typing
from typing import Any, Literal, TYPE_CHECKING

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
    SharingS3Update,
    SharingS3UpdateArgs,
    SharingS3UpdateResult,
    ZFSResourceCreateArgsData,
    ZFSResourceCreateProperties,
    ZFSResourceQuery,
)
from middlewared.common.attachment import LockableFSAttachmentDelegate
from middlewared.plugins.zfs.exceptions import ZFSPathAlreadyExistsException, ZFSPathNotFoundException
from middlewared.service import CallError, SharingService, ValidationErrors, private
import middlewared.sqlalchemy as sa
from middlewared.utils.path import FSLocation
from middlewared.utils.types import AuditCallback

from .grants import PrincipalNames, Principals, grant_principals, label_grants, principal_names, validate_grants
from .lifecycle import MISSING_ALERT, render_and_apply

if TYPE_CHECKING:
    from middlewared.main import Middleware

__all__ = ("SharingS3Service", "S3FSAttachmentDelegate")

AUDIT_ACTIONS: tuple[str, ...] = typing.get_args(S3AuditAction)

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


def is_ipv4_address(name: str) -> bool:
    try:
        ipaddress.IPv4Address(name)
    except ValueError:
        return False
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
        if ".." in data.name or is_ipv4_address(data.name):
            verrors.add(f"{schema}.name", "Bucket names may not contain adjacent dots or look like an IPv4 address.")
        filters: list[Any] = [["name", "=", data.name]]
        if old:
            filters.append(["id", "!=", old.id])
        if await self.query(filters, {"select": ["id"]}):
            verrors.add(f"{schema}.name", "A bucket with this name already exists.")

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
            if data.versioning == "OFF":
                verrors.add(
                    f"{schema}.versioning",
                    "Serving snapshots as versions requires versioning to be ENABLED or SUSPENDED.",
                )
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

        if (data.audit is not None or data.audit_overflow is not None) and not await self.middleware.call(
            "s3.audit_licensed"
        ):
            verrors.add(f"{schema}.audit", "Auditing the S3 service requires an Enterprise license.")

        await validate_grants(self.middleware, f"{schema}.grants", data.grants, verrors)

    @private
    async def resolve_owner(self, schema: str, username: str, verrors: ValidationErrors) -> int | None:
        """The owner's uid."""
        try:
            user = await self.middleware.call("user.get_user_obj", {"username": username})
        except KeyError:
            verrors.add(f"{schema}.owner", f"User {username!r} does not exist.")
            return None
        uid: int = user["pw_uid"]
        return uid

    @private
    def compress(self, data: SharingS3Entry, owner_uid: int) -> dict[str, Any]:
        row = data.model_dump(exclude={"id", "locked", "owner"})
        row["grants"] = [g.model_dump(exclude={"name"}) for g in data.grants]
        row["owner_uid"] = owner_uid
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
        service requires, and must not exist beforehand. Objects live in its
        ``s3data`` directory, which the S3 service creates on its next start
        owned by ``owner``. Under the ``S3`` and ``MULTIPROTOCOL`` permissions
        models every object is written under the account that put it, so a
        grantee other than the owner can write only where that directory's
        permissions let the account write; set an ACL on it as for any share,
        or choose ``S3_BUCKET_OWNER_ENFORCED``, under which every object is
        written as the owner and the grants alone decide. Grants may be given
        in the same call. Registering a bucket restarts the S3 service,
        draining in-flight requests for up to 30 seconds.
        """
        verrors = ValidationErrors()
        await self.validate(data, "sharing_s3_create", verrors)
        owner_uid = await self.resolve_owner("sharing_s3_create", data.owner, verrors)
        if await self.query([["dataset", "=", data.dataset]], {"select": ["id"]}):
            verrors.add("sharing_s3_create.dataset", "Another bucket already uses this dataset.")
        verrors.check()
        assert owner_uid is not None

        await self.create_dataset("sharing_s3_create", data.dataset)
        try:
            id_ = await self.middleware.call("datastore.insert", self._config.datastore, self.compress(data, owner_uid))
            await render_and_apply(self.middleware)
        except Exception:
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

        ``grants`` replaces the bucket's whole grant list. Changing the owner,
        the grants or the audit settings reloads the S3 service; changing
        anything the service registers at startup, or enabling and disabling
        the bucket, restarts it.
        """
        old = await self.get_instance(id_)
        audit_callback(old.name)

        new = old.updated(data)
        verrors = ValidationErrors()
        await self.validate(new, "sharing_s3_update", verrors, old)
        # an owner given by name is compared by the uid it resolves to: a
        # renamed account is the same owner, a deleted and recreated one
        # under the old name is not
        owner_uid = old.owner_uid
        if "owner" in data.model_dump(exclude_unset=True):
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
        if not await self.middleware.call("s3.audit_licensed"):
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
    service = "truenas_s3"
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
