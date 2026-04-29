from __future__ import annotations

import errno
import os
from typing import Any

from middlewared.api.current import TunableCreate, TunableEntry, TunableUpdate
from middlewared.service import CRUDServicePart, ValidationErrors
from middlewared.service_exception import CallError
import middlewared.sqlalchemy as sa

from .utils import (
    generate_sysctl,
    get_sysctl,
    get_sysctls,
    handle_tunable_change,
    reset_sysctl,
    reset_zfs_parameter,
    set_sysctl,
    set_zfs_parameter,
    update_initramfs,
    zfs_parameter_path,
    zfs_parameter_value,
)


class TunableModel(sa.Model):
    __tablename__ = "system_tunable"

    id = sa.Column(sa.Integer(), primary_key=True)
    tun_type = sa.Column(sa.String(20))
    tun_var = sa.Column(sa.String(128), unique=True)
    tun_value = sa.Column(sa.String(512))
    tun_orig_value = sa.Column(sa.String(512))
    tun_comment = sa.Column(sa.String(100))
    tun_enabled = sa.Column(sa.Boolean(), default=True)


class TunableServicePart(CRUDServicePart[TunableEntry]):
    _datastore = "system.tunable"
    _datastore_prefix = "tun_"
    _entry = TunableEntry

    def compress(self, data: dict[str, Any]) -> dict[str, Any]:
        data.pop("update_initramfs", None)
        return data

    async def do_create(self, data: TunableCreate) -> TunableEntry:
        failover_licensed = await self._check_ha()

        verrors = ValidationErrors()

        if await self.query([("var", "=", data.var)]):
            verrors.add(
                "tunable_create.var",
                f"Tunable {data.var!r} already exists in database.",
                errno.EEXIST,
            )

        if data.type == "SYSCTL":
            if data.var not in await self.to_thread(get_sysctls):
                verrors.add(
                    "tunable_create.var",
                    f"Sysctl {data.var!r} does not exist in kernel.",
                    errno.ENOENT,
                )

        if data.type == "UDEV" and "truenas" in data.var:
            verrors.add(
                "tunable_create.var",
                "Udev rules with `truenas` in their name are not allowed.",
                errno.EPERM,
            )

        if data.type == "ZFS":
            if not await self.to_thread(os.path.exists, zfs_parameter_path(data.var)):
                verrors.add(
                    "tunable_create.var",
                    f"ZFS module does not accept {data.var!r} parameter.",
                    errno.ENOENT,
                )

        verrors.check()

        orig_value = ""
        if data.type == "SYSCTL":
            orig_value = await self.to_thread(get_sysctl, data.var)
        elif data.type == "ZFS":
            orig_value = await self.to_thread(zfs_parameter_value, data.var)

        create_data = data.model_dump()
        create_data["orig_value"] = orig_value

        entry = await self._create(create_data)

        try:
            if entry.type == "SYSCTL":
                if entry.enabled:
                    await generate_sysctl(self.middleware, failover_licensed)
                    await self.to_thread(set_sysctl, self.middleware, entry.var, entry.value, failover_licensed)
            elif entry.type == "ZFS":
                if entry.enabled:
                    await self.to_thread(set_zfs_parameter, self.middleware, entry.var, entry.value, failover_licensed)
                    if data.update_initramfs:
                        await update_initramfs(self.middleware, failover_licensed)
            else:
                await handle_tunable_change(self.middleware, entry.model_dump(), failover_licensed)
        except Exception:
            await self._delete(entry.id)
            raise

        return entry

    async def do_update(self, id_: int, data: TunableUpdate) -> TunableEntry:
        old = await self.get_instance(id_)

        failover_licensed = await self._check_ha()

        new = old.updated(data)

        if old.model_dump(exclude={"update_initramfs"}) == new.model_dump(exclude={"update_initramfs"}):
            return old

        await self._update(id_, new.model_dump())

        try:
            if new.type == "SYSCTL":
                await generate_sysctl(self.middleware, failover_licensed)

                if new.enabled:
                    await self.to_thread(set_sysctl, self.middleware, new.var, new.value, failover_licensed)
                else:
                    await self.to_thread(reset_sysctl, self.middleware, new, failover_licensed)
            elif new.type == "ZFS":
                if new.enabled:
                    await self.to_thread(set_zfs_parameter, self.middleware, new.var, new.value, failover_licensed)
                else:
                    await self.to_thread(reset_zfs_parameter, self.middleware, new, failover_licensed)

                if data.update_initramfs:
                    await update_initramfs(self.middleware, failover_licensed)
            else:
                await handle_tunable_change(self.middleware, new.model_dump(), failover_licensed)
        except Exception:
            await self._update(id_, old.model_dump())
            raise

        return await self.get_instance(id_)

    async def do_delete(self, id_: int) -> None:
        entry = await self.get_instance(id_)

        failover_licensed = await self._check_ha()

        await self._delete(entry.id)

        if entry.type == "SYSCTL":
            await generate_sysctl(self.middleware, failover_licensed)
            await self.to_thread(reset_sysctl, self.middleware, entry, failover_licensed)
        elif entry.type == "ZFS":
            await self.to_thread(reset_zfs_parameter, self.middleware, entry, failover_licensed)
            await update_initramfs(self.middleware, failover_licensed)
        else:
            await handle_tunable_change(self.middleware, entry.model_dump(), failover_licensed)

    async def _check_ha(self) -> bool:
        failover_licensed = await self.middleware.call("failover.licensed")
        if failover_licensed:
            if (status := await self.middleware.call("failover.status")) != "MASTER":
                raise CallError(f"Updating tunables is only allowed on MASTER mode. The current node is {status!r}.")

            if not await self.middleware.call("failover.remote_connected"):
                raise CallError("Updating tunables is only allowed when remote node is up. The remote node is down.")

        return bool(failover_licensed)
