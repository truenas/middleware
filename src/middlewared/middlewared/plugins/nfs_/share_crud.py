from __future__ import annotations

from typing import Any

from middlewared.api.current import NfsShareCreate, NfsShareUpdate, SharingNFSEntry
from middlewared.service import ServiceChangeMixin, SharingServicePart, ValidationErrors
import middlewared.sqlalchemy as sa
from middlewared.utils.types import AuditCallback

from .share_validate import validate_nfs_share


class NFSShareModel(sa.Model):
    __tablename__ = "sharing_nfs_share"

    id = sa.Column(sa.Integer(), primary_key=True)
    nfs_path = sa.Column(sa.Text())
    nfs_dataset = sa.Column(sa.String(255), nullable=True)
    nfs_relative_path = sa.Column(sa.String(255), nullable=True)
    nfs_aliases = sa.Column(sa.JSON(list))
    nfs_comment = sa.Column(sa.String(120))
    nfs_network = sa.Column(sa.Text())
    nfs_hosts = sa.Column(sa.Text())
    nfs_ro = sa.Column(sa.Boolean(), default=False)
    nfs_maproot_user = sa.Column(sa.String(120), nullable=True, default="")
    nfs_maproot_group = sa.Column(sa.String(120), nullable=True, default="")
    nfs_mapall_user = sa.Column(sa.String(120), nullable=True, default="")
    nfs_mapall_group = sa.Column(sa.String(120), nullable=True, default="")
    nfs_security = sa.Column(sa.MultiSelectField())
    nfs_expose_snapshots = sa.Column(sa.Boolean(), default=False)
    nfs_enabled = sa.Column(sa.Boolean(), default=True)


class SharingNFSServicePart(SharingServicePart[SharingNFSEntry], ServiceChangeMixin):
    _datastore = "sharing.nfs_share"
    _datastore_prefix = "nfs_"
    _entry = SharingNFSEntry

    include_tier_info = True
    readonly_field = "ro"

    async def sharing_task_extend(self, data: dict[str, Any], service_context: Any) -> dict[str, Any]:
        data["networks"] = data.pop("network").split()
        data["hosts"] = data["hosts"].split()
        data["security"] = [s.upper() for s in data["security"]]
        return data

    async def compress(self, data: dict[str, Any]) -> dict[str, Any]:
        data["network"] = " ".join(data.pop("networks"))
        data["hosts"] = " ".join(data["hosts"])
        data["security"] = [s.lower() for s in data["security"]]
        for computed in ("id", self.locked_field, "tier"):
            data.pop(computed, None)
        return data

    async def do_create(self, data: NfsShareCreate) -> SharingNFSEntry:
        entry = await self._create(await self._validated_row("sharingnfs_create", data))

        await self._service_change("nfs", "reload")

        return entry

    async def do_update(
        self,
        audit_callback: AuditCallback,
        id_: int,
        data: NfsShareUpdate,
    ) -> SharingNFSEntry:
        old = await self.get_instance(id_)
        audit_callback(old.path)

        new = old.updated(data)
        entry = await self._update(id_, await self._validated_row("sharingnfs_update", new, exclude_id=id_))

        if entry.path != old.path:
            await self._remove_share_alerts(old.path)

        await self._service_change("nfs", "reload")

        return entry

    async def _validated_row(
        self,
        schema_name: str,
        data: SharingNFSEntry,
        exclude_id: int | None = None,
    ) -> dict[str, Any]:
        verrors = ValidationErrors()
        await validate_nfs_share(self, data, schema_name, verrors, exclude_id)
        verrors.check()

        row = data.model_dump()
        row["dataset"] = data.dataset
        row["relative_path"] = data.relative_path
        return row

    async def do_delete(self, audit_callback: AuditCallback, id_: int) -> None:
        share = await self.get_instance(id_)
        audit_callback(share.path)

        await self._delete(id_)
        await self._remove_share_alerts(share.path)

        await self._service_change("nfs", "reload")

    async def _remove_share_alerts(self, path: str) -> None:
        await self.call2(self.s.alert.oneshot_delete, "NFSNetworkListExcessive", {"sharePath": path})
        await self.call2(self.s.alert.oneshot_delete, "NFSHostListExcessive", {"sharePath": path})
