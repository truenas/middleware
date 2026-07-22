from __future__ import annotations

import asyncio
import datetime
import errno
from typing import Any, NoReturn

from truenas_bootenv import naming as be_naming
from truenas_bootenv.errors import BEError, BEExists, BENotFound

from middlewared.api.current import (
    BootEnvironmentActivate,
    BootEnvironmentClone,
    BootEnvironmentDestroy,
    BootEnvironmentEntry,
    BootEnvironmentKeep,
    QueryOptions,
)
from middlewared.service import CRUDServicePart
from middlewared.service_exception import CallError, ValidationError
from middlewared.utils.filter_list import filter_list
from middlewared.utils.size import format_size

# Serializes every operation that mutates the boot environment
# origin/clone graph: activate/clone/destroy plus keep and the boot-time
# dataset promotion. The engine re-checks the destructive guards
# (running/activated) against fresh state inside its own calls; this
# lock guarantees those mutations cannot interleave, so a destroy and
# an activate racing each other resolve to one consistent winner.
BE_MUTATE_LOCK = asyncio.Lock()


class BootEnvironmentServicePart(CRUDServicePart[BootEnvironmentEntry, str]):
    _entry = BootEnvironmentEntry

    async def query(  # type: ignore[override]
        self, filters: list[Any], options: QueryOptions
    ) -> list[BootEnvironmentEntry] | BootEnvironmentEntry | int:
        bp_name = await self.call2(self.s.boot.pool_name)
        try:
            info = await self.call2(self.s.boot.environment.be_list_impl, bp_name)
        except BENotFound:
            # <pool>/ROOT can be missing where middlewared runs
            # without a TrueNAS install (development containers) or on
            # a system under repair; the query read path must report
            # that as "no boot environments", not break every caller.
            # Anything else must surface. Run the empty list through
            # filter_list so count/get options keep their contract.
            return filter_list([], filters, options, self._entry)

        entries = []
        for i in info:
            entries.append(
                BootEnvironmentEntry(
                    id=i.name,
                    dataset=i.dataset,
                    active=i.active,
                    activated=i.activated,
                    created=datetime.datetime.fromtimestamp(i.created, datetime.timezone.utc),
                    used_bytes=i.used_bytes,
                    used=format_size(i.used_bytes),
                    keep=bool(i.keep),
                    can_activate=i.can_activate,
                )
            )
        return filter_list(entries, filters, options, self._entry)

    async def get_instance(self, id_: str, extra: dict[str, Any] | None = None) -> BootEnvironmentEntry:
        return await self.get_be("boot.environment", id_)

    async def get_be(self, schema_name: str, name: str) -> BootEnvironmentEntry:
        results = await self.query([["id", "=", name]], QueryOptions())
        matches = results if isinstance(results, list) else []
        if not matches:
            raise ValidationError(schema_name, f"{name!r} not found")
        return matches[0]

    async def read_back(self, schema_name: str, be_id: str) -> BootEnvironmentEntry:
        # the mutation is fully committed by the time this runs; a
        # transient failure reading the result back must not be
        # reported as the operation having failed
        try:
            return await self.get_be(schema_name, be_id)
        except Exception as e:
            raise CallError(
                f"{schema_name} succeeded, but reading back the "
                f"resulting boot environment failed: {e!r}"
            ) from e

    def map_be_error(self, schema_name: str, error: BEError) -> NoReturn:
        if isinstance(error, BEExists):
            raise ValidationError(schema_name, str(error), errno.EEXIST)
        if isinstance(error, BENotFound):
            raise ValidationError(schema_name, str(error))
        raise CallError(
            str(error), getattr(error, "errno", None) or errno.EFAULT,
        )

    async def set_grub_marker(self, schema_name: str, fatal: bool) -> None:
        # record the regeneration intent BEFORE mutating, so a
        # middlewared death between the ZFS commit and the menu write
        # is reconciled by setup(). The marker is a crash-recovery aid,
        # not a precondition: a failure to write it honors the same
        # fatal contract as the menu write itself.
        bp_name = await self.call2(self.s.boot.pool_name)
        try:
            await self.call2(
                self.s.boot.environment.be_grub_marker_impl, bp_name, "set",
            )
        except Exception as e:
            if fatal:
                self.logger.error(
                    "%s: could not set the boot menu regeneration "
                    "marker", schema_name, exc_info=True,
                )
                raise CallError(
                    f"Could not record the boot menu regeneration intent "
                    f"({e!r}); nothing was changed"
                ) from e
            self.logger.warning(
                "%s: could not set the boot menu regeneration marker",
                schema_name, exc_info=True,
            )

    async def regenerate_grub(self, schema_name: str, fatal: bool) -> None:
        # bootfs only orders the grub menu at grub-mkconfig time; the
        # regenerated menu is what actually changes the next boot, so
        # activate must fail loudly if it cannot be written. After
        # clone/destroy a stale menu is cosmetic (the entry appears or
        # disappears on the next regeneration), so failure only logs.
        # Every caller has already recorded the intent marker via
        # set_grub_marker; this only clears it after a durable write.
        bp_name = await self.call2(self.s.boot.pool_name)
        try:
            await self.middleware.call("etc.generate", "grub")
        except Exception as e:
            if fatal:
                self.logger.error(
                    "%s: boot menu regeneration failed", schema_name,
                    exc_info=True,
                )
                raise CallError(
                    f"The boot menu could not be regenerated ({e!r}); "
                    "re-run activate to retry"
                ) from e
            self.logger.warning(
                "%s: etc.generate('grub') failed; the boot menu will "
                "refresh on the next regeneration", schema_name,
                exc_info=True,
            )
            return
        try:
            # The regenerated grub.cfg is not crash-durable until its
            # transaction group commits (see engine.sync_boot_pool).
            # The menu itself was regenerated, so a sync failure is
            # only a durability warning, never a reason to roll
            # anything back.
            await self.call2(
                self.s.boot.environment.be_sync_pool_impl, bp_name,
            )
            await self.call2(
                self.s.boot.environment.be_grub_marker_impl, bp_name, "clear",
            )
        except Exception:
            self.logger.warning(
                "%s: boot pool sync after menu regeneration failed; the "
                "new menu is written but not yet crash-durable",
                schema_name, exc_info=True,
            )

    async def activate(self, data: BootEnvironmentActivate) -> BootEnvironmentEntry:
        be = await self.get_be("boot.environment.activate", data.id)
        if not be.can_activate:
            raise ValidationError(
                "boot.environment.activate", f"{data.id!r} can not be activated"
            )
        bp_name = await self.call2(self.s.boot.pool_name)
        async with BE_MUTATE_LOCK:
            previous = await self.call2(
                self.s.boot.environment.be_pool_bootfs_impl, bp_name,
            )
            await self.set_grub_marker("boot.environment.activate", fatal=True)
            # the engine call is inside the compensated block too: it can
            # fail after it has already written bootfs (the ZFS binding
            # logs pool history once the property is committed, so it can
            # raise on a durable change). Left alone, bootfs would point at
            # a boot environment whose menu was never written, and the
            # marker reconcile at the next start would then make this
            # "failed" activate quietly take effect.
            try:
                try:
                    await self.call2(
                        self.s.boot.environment.be_activate_impl, be.dataset,
                    )
                except BEError as e:
                    self.map_be_error("boot.environment.activate", e)
                await self.regenerate_grub(
                    "boot.environment.activate", fatal=True,
                )
            except BaseException:
                # BaseException, not Exception: the engine runs in a worker
                # thread that is not cancelled with us, so a client
                # disconnect or a middlewared restart raises CancelledError
                # here while that thread goes on to commit bootfs. Without
                # this, the abandoned activate would still be sitting in
                # bootfs for setup()'s marker reconcile to turn into the
                # boot default.
                # the on-disk menu still points at the previous default;
                # point bootfs back at it so the two agree and the
                # destroy guard keeps protecting what actually boots.
                # Compare-and-set: only undo our own write, never a
                # concurrent external writer's.
                if previous and previous != be.dataset:
                    try:
                        current = await self.call2(
                            self.s.boot.environment.be_pool_bootfs_impl,
                            bp_name,
                        )
                        if current == be.dataset:
                            await self.call2(
                                self.s.boot.environment.be_set_bootfs_impl,
                                bp_name, previous,
                            )
                    except Exception:
                        self.logger.error(
                            "boot.environment.activate: could not restore "
                            "previous bootfs %r", previous, exc_info=True,
                        )
                raise
        return await self.read_back("boot.environment.activate", data.id)

    async def clone(self, data: BootEnvironmentClone) -> BootEnvironmentEntry:
        be = await self.get_be("boot.environment.clone", data.id)
        if not be.can_activate:
            raise ValidationError(
                "boot.environment.clone",
                f"{data.id!r} has no kernel version; the clone would "
                "never be bootable",
            )
        bp_name = await self.call2(self.s.boot.pool_name)
        try:
            target_dataset = be_naming.be_dataset(bp_name, data.target)
        except ValueError as e:
            raise ValidationError(
                "boot.environment.clone", f"Invalid target name: {e}",
            )
        results = await self.query([["id", "=", data.target]], QueryOptions())
        if results:
            raise ValidationError(
                "boot.environment.clone",
                f"{data.target!r} already exists (an incomplete boot "
                "environment from an interrupted clone can be removed "
                "with boot.environment.destroy)",
                errno.EEXIST,
            )
        async with BE_MUTATE_LOCK:
            await self.set_grub_marker("boot.environment.clone", fatal=False)
            try:
                await self.call2(
                    self.s.boot.environment.be_create_impl,
                    be.dataset, target_dataset,
                )
            except BEError as e:
                self.map_be_error("boot.environment.clone", e)
            await self.regenerate_grub("boot.environment.clone", fatal=False)
        return await self.read_back("boot.environment.clone", data.target)

    async def destroy(self, data: BootEnvironmentDestroy) -> None:
        be = await self.get_be("boot.environment.destroy", data.id)
        if be.active:
            raise ValidationError(
                "boot.environment.destroy",
                "Deleting the active boot environment is not allowed",
            )
        if be.activated:
            raise ValidationError(
                "boot.environment.destroy",
                "Deleting the activated boot environment is not allowed",
            )
        async with BE_MUTATE_LOCK:
            await self.set_grub_marker("boot.environment.destroy", fatal=False)
            try:
                await self.call2(
                    self.s.boot.environment.be_destroy_impl, be.dataset,
                )
            except BEError as e:
                self.map_be_error("boot.environment.destroy", e)
            await self.regenerate_grub("boot.environment.destroy", fatal=False)

    async def keep(self, data: BootEnvironmentKeep) -> BootEnvironmentEntry:
        async with BE_MUTATE_LOCK:
            # the lookup stays inside the lock: set_keep does no
            # engine-side re-check, so this is what stops a concurrent
            # destroy from removing the dataset between lookup and write
            be = await self.get_be("boot.environment.keep", data.id)
            try:
                await self.call2(
                    self.s.boot.environment.be_set_keep_impl,
                    be.dataset, data.value,
                )
            except BEError as e:
                self.map_be_error("boot.environment.keep", e)
        return await self.read_back("boot.environment.keep", data.id)

    async def promote_current_datasets(self) -> None:
        async with BE_MUTATE_LOCK:
            # no active BE is normal in dev/rescue boots where / is
            # not ZFS; a get=True query would raise instead
            results = await self.query([["active", "=", True]], QueryOptions())
            active = results if isinstance(results, list) else []
            if not active:
                return
            dataset = active[0].dataset
            promoted, failures = await self.call2(
                self.s.boot.environment.be_promote_children_impl, dataset,
            )
            for name, origin in promoted:
                self.logger.info(
                    "%r: promoted; it was a clone of %r", name, origin,
                )
            for name, error in failures:
                self.logger.error(
                    "%r: unexpected error promoting dataset: %s", name, error,
                )
