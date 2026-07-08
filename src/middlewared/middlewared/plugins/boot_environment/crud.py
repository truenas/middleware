from __future__ import annotations

import datetime
import errno
import json
import os
import subprocess
from typing import Any

from truenas_os_pyutils.mount import statmount

from middlewared.api.current import (
    BootEnvironmentActivate,
    BootEnvironmentClone,
    BootEnvironmentDestroy,
    BootEnvironmentEntry,
    BootEnvironmentKeep,
    QueryOptions,
    ZFSResourceQuery,
)
from middlewared.plugins.pool_.utils import UpdateImplArgs
from middlewared.service import CRUDServicePart
from middlewared.service_exception import ValidationError
from middlewared.utils.filter_list import filter_list
from middlewared.utils.size import format_size

from .utils import run_zectl_cmd


class BootEnvironmentServicePart(CRUDServicePart[BootEnvironmentEntry, str]):
    _entry = BootEnvironmentEntry

    async def _zfs_get_props(self) -> tuple[list[dict[str, Any]], str]:
        rv = []
        bp_name = await self.middleware.call("boot.pool_name")
        for i in await self.call2(
            self.s.zfs.resource.query_impl,
            ZFSResourceQuery(
                paths=[f"{bp_name}/ROOT"],
                get_children=True,
                properties=["used", "creation"],
                get_user_properties=True,
            ),
        ):
            if i["name"].count("/") == 2:
                # boot-pool/ROOT/25.04.1
                # and not boot-pool/ROOT/25.04.1/blah
                rv.append(i)
        return rv, bp_name

    async def query(  # type: ignore[override]
        self, filters: list[Any], options: QueryOptions
    ) -> list[BootEnvironmentEntry] | BootEnvironmentEntry | int:
        try:
            info, bp_name = await self._zfs_get_props()
        except Exception:
            return []

        active_be = (await self.to_thread(statmount, path="/"))["mount_source"]
        activated_be = (
            await self.middleware.call("zpool.query_impl", {"pool_names": [bp_name], "properties": ["bootfs"]})
        )[0]["properties"]["bootfs"]["value"]

        entries = []
        for i in info:
            props = i["properties"]
            entries.append(
                BootEnvironmentEntry(
                    id=os.path.basename(i["name"]),
                    dataset=i["name"],
                    active=active_be == i["name"],
                    activated=activated_be == i["name"],
                    created=datetime.datetime.utcfromtimestamp(props["creation"]["value"]),
                    used_bytes=props["used"]["value"],
                    used=format_size(props["used"]["value"]),
                    keep=i["user_properties"].get("zectl:keep") == "True",
                    can_activate=i["user_properties"].get("truenas:kernel_version") != "-",
                )
            )
        return filter_list(entries, filters, options, self._entry)

    async def get_instance(self, id_: str, extra: dict[str, Any] | None = None) -> BootEnvironmentEntry:
        results = await self.query([["id", "=", id_]], QueryOptions())
        matches = results if isinstance(results, list) else []
        if not matches:
            raise ValidationError("boot.environment", f"{id_!r} not found")
        return matches[0]

    async def get_be(self, schema_name: str, name: str) -> BootEnvironmentEntry:
        results = await self.query([["id", "=", name]], QueryOptions())
        matches = results if isinstance(results, list) else []
        if not matches:
            raise ValidationError(schema_name, f"{name!r} not found")
        return matches[0]

    async def ensure_be_absent(self, schema_name: str, name: str) -> None:
        results = await self.query([["id", "=", name]], QueryOptions())
        matches = results if isinstance(results, list) else []
        if matches:
            raise ValidationError(schema_name, f"{name!r} already exists", errno.EEXIST)

    async def activate(self, data: BootEnvironmentActivate) -> BootEnvironmentEntry:
        info = await self.get_be("boot.environment.activate", data.id)
        if info.activated:
            raise ValidationError("boot.environment.activate", f"{data.id!r} is already activated")
        if not info.can_activate:
            raise ValidationError("boot.environment.activate", f"{data.id!r} can not be activated")
        await self.to_thread(run_zectl_cmd, ["activate", data.id])
        return await self.get_be("boot.environment.activate", data.id)

    async def clone(self, data: BootEnvironmentClone) -> BootEnvironmentEntry:
        be = await self.get_be("boot.environment.clone", data.id)
        await self.ensure_be_absent("boot.environment.clone", data.target)
        await self.to_thread(run_zectl_cmd, ["create", "-r", "-e", be.dataset, data.target])
        return await self.get_be("boot.environment.clone", data.target)

    async def destroy(self, data: BootEnvironmentDestroy) -> None:
        be = await self.get_be("boot.environment.destroy", data.id)
        if be.active:
            raise ValidationError(
                "boot.environment.destroy",
                "Deleting the active boot environment is not allowed",
            )
        await self.to_thread(run_zectl_cmd, ["destroy", data.id])

    async def keep(self, data: BootEnvironmentKeep) -> BootEnvironmentEntry:
        be = await self.get_be("boot.environment.keep", data.id)
        await self.middleware.call(
            "pool.dataset.update_impl",
            UpdateImplArgs(name=be.dataset, uprops={"zectl:keep": str(data.value)}),
        )
        return await self.get_be("boot.environment.keep", data.id)

    async def promote_current_datasets(self) -> None:
        active = await self.query([["active", "=", True]], QueryOptions(get=True))
        if not isinstance(active, BootEnvironmentEntry):
            return

        be_datasets = await self.to_thread(
            subprocess.run,
            f"zfs list -o origin -r {active.dataset} -j",
            capture_output=True,
            shell=True,
        )
        for ds, info in json.loads(be_datasets.stdout)["datasets"].items():
            if ds.startswith(f"{active.dataset}/"):
                origin = info["properties"]["origin"]["value"]
                if origin != "-":
                    self.logger.info("Promoting dataset %r as it is a clone of %r", ds, origin)
                    try:
                        await self.middleware.call("pool.dataset.promote", ds)
                    except Exception:
                        self.logger.exception("Unexpected error promoting %r", ds)
