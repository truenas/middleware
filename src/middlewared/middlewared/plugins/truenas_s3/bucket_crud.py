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
import typing
from typing import Any, Literal, TYPE_CHECKING

from middlewared.api import api_method
from middlewared.api.current import (
    S3AuditAction,
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

from .grants import grant_principals, label_grants, principal_names, validate_grants
from .lifecycle import render_and_apply

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

# the ACL on a fresh bucket's data directory, the share root. Every write is
# published under the requester's own uid and no capability bypasses that
# check, so an ACL any grantee's uid satisfies is what leaves the S3 grants
# as the only gate. Inherited by the prefix directories requesters create
DATA_ACL = [
    {"tag": "owner@", "type": "ALLOW", "perms": {"BASIC": "FULL_CONTROL"}, "flags": {"BASIC": "INHERIT"}},
    {"tag": "group@", "type": "ALLOW", "perms": {"BASIC": "FULL_CONTROL"}, "flags": {"BASIC": "INHERIT"}},
    {"tag": "everyone@", "type": "ALLOW", "perms": {"BASIC": "MODIFY"}, "flags": {"BASIC": "INHERIT"}},
]


class SharingS3Model(sa.Model):
    __tablename__ = "truenas_s3_bucket"

    id = sa.Column(sa.Integer(), primary_key=True)
    name = sa.Column(sa.String(63), unique=True)
    dataset = sa.Column(sa.String(255), unique=True)
    enabled = sa.Column(sa.Boolean(), default=True)
    # the uid is the owner; its name is resolved when read, never stored,
    # so a renamed account reads as its new name and a reused name never
    # inherits a bucket
    owner_uid = sa.Column(sa.Integer())
    grants = sa.Column(sa.JSON(list), default=[])
    permissions_model = sa.Column(sa.String(16), default="S3")
    versioning = sa.Column(sa.String(16), default="OFF")
    object_lock = sa.Column(sa.Boolean(), default=False)
    object_lock_default_mode = sa.Column(sa.String(16), nullable=True)
    object_lock_default_days = sa.Column(sa.Integer(), nullable=True)
    # NULL inherits the service default; an empty list audits nothing
    audit = sa.Column(sa.JSON(None), nullable=True)
    audit_overflow = sa.Column(sa.String(16), nullable=True)


def data_dir(mountpoint: str) -> str:
    """The bucket root: objects sit one level below the mount point, beside
    the daemon's side tree, so a share over the objects never reaches it."""
    return f"{mountpoint}/data"


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
    async def bucket_extend_context(self, rows: list[dict[str, Any]], extra: dict[str, Any]) -> dict[str, Any]:
        """Every owner and grant principal across the rows, resolved once
        each rather than once per row."""
        uids = {row["owner_uid"] for row in rows}
        gids: set[int] = set()
        for row in rows:
            row_uids, row_gids = grant_principals(row["grants"])
            uids |= row_uids
            gids |= row_gids
        return await principal_names(self.middleware, uids, gids)

    @private
    async def bucket_extend(self, data: dict[str, Any], names: dict[str, dict[int, str]]) -> dict[str, Any]:
        data["owner"] = names["users"].get(data["owner_uid"], str(data["owner_uid"]))
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
            if data.permissions_model != "S3":
                verrors.add(
                    f"{schema}.permissions_model",
                    "Object lock requires the S3 permissions model: another protocol could rewrite a locked object.",
                )
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
    async def resolve_owner(self, schema: str, username: str, verrors: ValidationErrors) -> tuple[int, int] | None:
        """The owner's uid and primary gid."""
        try:
            user = await self.middleware.call("user.get_user_obj", {"username": username})
        except KeyError:
            verrors.add(f"{schema}.owner", f"User {username!r} does not exist.")
            return None
        return user["pw_uid"], user["pw_gid"]

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
    async def create_dataset(self, schema: str, name: str, owner: tuple[int, int]) -> str:
        """Create the bucket's dataset with the properties the S3 on-disk
        format requires, provision its data directory and return the mount
        point. The properties are stated here in full rather than inherited
        from any other layer's defaults; normalization and utf8only are
        internal-only create properties, which is what lets them override a
        parent that would otherwise pass its own values down."""
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
        mountpoint = await self.mountpoint(name)
        if mountpoint is None:
            await self.destroy_dataset(name)
            raise CallError(f"{name}: the new dataset has no usable mount point.")
        try:
            await self.provision_data(mountpoint, owner)
        except Exception:
            await self.destroy_dataset(name)
            raise
        return mountpoint

    @private
    async def provision_data(self, mountpoint: str, owner: tuple[int, int]) -> None:
        """The share root, owned by the bucket's owner and open to every
        grantee. The dataset root above it stays the daemon's: it holds the
        side tree, and a root the owner could write would let them rename
        the version history away."""
        uid, gid = owner
        await self.middleware.call("filesystem.mkdir", {"path": data_dir(mountpoint), "options": {"mode": "755"}})
        job = await self.middleware.call(
            "filesystem.setacl", {"path": data_dir(mountpoint), "dacl": DATA_ACL, "uid": uid, "gid": gid}
        )
        await job.wait(raise_error=True)

    @private
    async def chown_data(self, mountpoint: str, owner: tuple[int, int]) -> None:
        """Hand the share root to a new owner. Not recursive: what the old
        owner wrote stays theirs, as it would under any other share."""
        uid, gid = owner
        try:
            await self.middleware.call("filesystem.stat", data_dir(mountpoint))
        except CallError as e:
            if e.errno == errno.ENOENT:
                return
            raise
        job = await self.middleware.call("filesystem.chown", {"path": data_dir(mountpoint), "uid": uid, "gid": gid})
        await job.wait(raise_error=True)

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
        ``data`` directory, which is owned by ``owner`` and carries an
        inheritable ACL open to every grantee, so the grants are what decide
        access. Grants may be given in the same call. Registering a bucket
        restarts the S3 service, draining in-flight requests for up to 30
        seconds.
        """
        verrors = ValidationErrors()
        await self.validate(data, "sharing_s3_create", verrors)
        owner = await self.resolve_owner("sharing_s3_create", data.owner, verrors)
        if await self.query([["dataset", "=", data.dataset]], {"select": ["id"]}):
            verrors.add("sharing_s3_create.dataset", "Another bucket already uses this dataset.")
        verrors.check()
        assert owner is not None

        await self.create_dataset("sharing_s3_create", data.dataset, owner)
        try:
            id_ = await self.middleware.call("datastore.insert", self._config.datastore, self.compress(data, owner[0]))
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
        owner = None
        if "owner" in data.model_dump(exclude_unset=True):
            resolved = await self.resolve_owner("sharing_s3_update", new.owner, verrors)
            if resolved is not None and resolved[0] != old.owner_uid:
                owner = resolved
        verrors.check()

        if owner is not None and (mountpoint := await self.mountpoint(old.dataset)) is not None:
            await self.chown_data(mountpoint, owner)
        owner_uid = old.owner_uid if owner is None else owner[0]
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
        default = (await self.middleware.call("s3.config")).default_audit
        names = []
        for bucket in await self.query([["enabled", "=", True]]):
            mask = bucket.audit if bucket.audit is not None else default
            if mask:
                names.append(bucket.name)
        return names


class S3FSAttachmentDelegate(LockableFSAttachmentDelegate[SharingS3Entry]):
    name = "s3"
    title = "S3 Bucket"
    service = "truenas_s3"
    service_class = SharingS3Service

    async def restart_reload_services(self, attachments: list[SharingS3Entry]) -> None:
        # every path here is a registry change: a bucket disabled for an
        # export or lock, re-enabled on import or unlock, or deleted with
        # its dataset. The daemon pins a registered dataset's mount, so the
        # restart has to land before the ZFS operation that follows
        await render_and_apply(self.middleware, force_restart=True)


async def setup(middleware: Middleware) -> None:
    await middleware.call("pool.dataset.register_attachment_delegate", S3FSAttachmentDelegate(middleware))
