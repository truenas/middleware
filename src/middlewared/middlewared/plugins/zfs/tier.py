from __future__ import annotations

import errno
import typing
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from middlewared.main import Middleware

import truenas_pylibzfs
from truenas_zfstierd_client import (
    RewriteClient,
    RewriteClientException,
    enum_jobs,
    feature_is_licensed,
    get_info,
    get_last_job,
    get_resolved_failures,
)
from truenas_zfstierd_common import (
    AbortJobResult,
    CreateJobResult,
    InfoResult,
    JSONRPCErrorCode,
    RecoverResult,
    RewriteJobStatus,
)

from middlewared.api import api_method
from middlewared.api.current import (
    ZfsTierEntry,
    ZfsTierUpdateArgs,
    ZfsTierUpdateResult,
    ZfsTierRewriteJobCreateArgs,
    ZfsTierRewriteJobCreateResult,
    ZfsTierRewriteJobQueryArgs,
    ZfsTierRewriteJobQueryResult,
    ZfsTierRewriteJobStatusArgs,
    ZfsTierRewriteJobStatusResult,
    ZfsTierRewriteJobCancelArgs,
    ZfsTierRewriteJobCancelResult,
    ZfsTierRewriteJobRecoverArgs,
    ZfsTierRewriteJobRecoverResult,
    ZfsTierRewriteJobQueryEventSourceArgs,
    ZfsTierRewriteJobQueryEventSourceEvent,
    ZfsTierRewriteJobStatusEventSourceArgs,
    ZfsTierRewriteJobStatusEventSourceEvent,
    ZfsTierDatasetSetTierArgs,
    ZfsTierDatasetSetTierResult,
    ZfsTierRewriteJobFailuresArgs,
    ZfsTierRewriteJobFailuresResult,
    ZFSResourceQuery,
)
from middlewared.event import TypedEventSource
from middlewared.plugins.pool_.utils import UpdateImplArgs
from middlewared.service import CallError, ConfigServicePart, GenericConfigService, private, ValidationError
from middlewared.service.decorators import pass_thread_local_storage
import middlewared.sqlalchemy as sa
from middlewared.utils.filter_list import filter_list


SPECIAL_SMALL_BLOCKS_PERFORMANCE = str(16 * 1024 * 1024)  # 16 MiB
SPECIAL_SMALL_BLOCKS_REGULAR = "0"

_DATASET_NOT_FOUND = (
    object()
)  # sentinel: dataset does not exist (distinct from None = pool has no SPECIAL vdev)


def _raise_client_error(e: RewriteClientException, field: str) -> None:
    """Convert a RewriteClientException to an appropriate middleware error."""
    if e.code == JSONRPCErrorCode.DATASET_NOT_FOUND:
        raise ValidationError(field, e.message, errno.ENOENT)
    if e.code == JSONRPCErrorCode.JOB_NOT_FOUND:
        raise ValidationError(field, e.message, errno.ENOENT)
    if e.code == JSONRPCErrorCode.JOB_ALREADY_EXISTS:
        raise ValidationError(field, e.message, errno.EEXIST)
    raise CallError(str(e))


class ZfsTierModel(sa.Model):
    __tablename__ = "zfs_tier"

    id = sa.Column(sa.Integer(), primary_key=True)
    enabled = sa.Column(sa.Boolean(), default=False)
    max_concurrent_jobs = sa.Column(sa.Integer(), default=2)
    min_available_space = sa.Column(sa.Integer(), default=0)
    special_class_metadata_reserve_pct = sa.Column(sa.Integer(), default=25)


def _map_info_result(info: InfoResult) -> dict[str, typing.Any]:
    """Build a ZfsTierRewriteJobStatusEntry dict from a RewriteClient InfoResult."""
    stats: dict[str, typing.Any] | None = None
    if info.stats:
        stats = {
            "start_time": info.stats.start_time,
            "initial_time": info.stats.initial_time,
            "update_time": info.stats.update_time,
            "count_items": info.stats.count_items,
            "count_bytes": info.stats.count_bytes,
            "total_items": info.stats.total_items,
            "total_bytes": info.stats.total_bytes,
            "failures": info.stats.failures,
            "success": info.stats.success,
            "parent": info.stats.parent,
            "name": info.stats.name,
        }
    return {
        "tier_job_id": f"{info.dataset_name}@{info.job_uuid}",
        "dataset_name": info.dataset_name,
        "job_uuid": info.job_uuid,
        "status": info.status,
        "stats": stats,
        "error": info.error,
    }


def _map_create_result(result: CreateJobResult) -> dict[str, typing.Any]:
    """Build a ZfsTierRewriteJobEntry dict from a RewriteClient CreateJobResult."""
    return {
        "tier_job_id": f"{result.dataset_name}@{result.job_uuid}",
        "dataset_name": result.dataset_name,
        "job_uuid": result.job_uuid,
        "status": result.status,
    }


def _map_recover_result(result: RecoverResult) -> dict[str, typing.Any]:
    """Build a ZfsTierRewriteJobEntry dict from a RewriteClient RecoverResult."""
    return {
        "tier_job_id": f"{result.dataset_name}@{result.job_uuid}",
        "dataset_name": result.dataset_name,
        "job_uuid": result.job_uuid,
        "status": result.status,
    }


def _map_cancel_result(result: AbortJobResult) -> dict[str, typing.Any]:
    """Build a ZfsTierRewriteJobEntry dict from a RewriteClient CancelJobResult."""
    return {
        "tier_job_id": f"{result.dataset_name}@{result.job_uuid}",
        "dataset_name": result.dataset_name,
        "job_uuid": result.job_uuid,
        "status": result.status,
    }


def _bulk_tier_map(lzh: typing.Any, dataset_names: list[str]) -> dict[str, typing.Any]:
    """
    Core tier-map computation: given an open lzh handle and a list of dataset
    names, returns {dataset_name: TierInfo|None} without checking license or
    enabled flag (callers must do those checks).
    """
    pool_special_cache: dict[str, bool] = {}
    result: dict[str, typing.Any] = {}
    for ds in dataset_names:
        try:
            rsrc = lzh.open_resource(name=ds)
        except truenas_pylibzfs.ZFSException as e:
            if e.code == truenas_pylibzfs.ZFSError.EZFS_NOENT:
                result[ds] = _DATASET_NOT_FOUND
                continue
            raise
        result[ds] = get_dataset_tier_info_cached(rsrc, pool_special_cache)
    return result


def get_dataset_tier_info_cached(
    hdl: typing.Any,
    pool_special_cache: dict[str, bool],
) -> dict[str, typing.Any] | None:
    """
    Returns TierInfo for a single dataset using a caller-maintained pool cache.
    pool_special_cache is mutated: {pool_name -> has_special_vdevs}.
    Does not check license or enabled flag — caller must do that.
    """
    pool_name = hdl.name.split("/")[0]

    if pool_name not in pool_special_cache:
        try:
            pool = hdl.open_pool()
            props = pool.get_properties(
                properties={truenas_pylibzfs.ZPOOLProperty.CLASS_SPECIAL_SIZE}
            )
            slot = props.class_special_size
            pool_special_cache[pool_name] = slot is not None and slot.value > 0
        except Exception:
            pool_special_cache[pool_name] = False

    if not pool_special_cache[pool_name]:
        return None

    try:
        dprops = hdl.get_properties(
            properties={
                truenas_pylibzfs.ZFSProperty.SPECIAL_SMALL_BLOCKS,
                truenas_pylibzfs.ZFSProperty.RECORDSIZE,
            }
        )
        ssb_slot = dprops.special_small_blocks
        ssb_value = ssb_slot.value if ssb_slot is not None else 0
        rs_slot = dprops.recordsize
        rs_value = rs_slot.value if rs_slot is not None else 0
        tier_type = (
            "PERFORMANCE" if rs_value > 0 and ssb_value >= rs_value else "REGULAR"
        )

        tier_job = None
        try:
            last = get_last_job(hdl.name)
            tier_job = {
                "tier_job_id": f"{last.dataset_name}@{last.job_uuid}",
                "dataset_name": last.dataset_name,
                "job_uuid": last.job_uuid,
                "status": last.status,
            }
        except KeyError:
            pass

        return {"tier_type": tier_type, "tier_job": tier_job}
    except Exception:
        return None


class ZfsTierRewriteJobStatusEventSource(
    TypedEventSource[ZfsTierRewriteJobStatusEventSourceArgs]
):
    """
    Subscribe to real-time status updates for a ZFS rewrite job on the specified dataset.
    Polls every 2 seconds and emits a CHANGED event when status or statistics change.
    """

    args = ZfsTierRewriteJobStatusEventSourceArgs
    event = ZfsTierRewriteJobStatusEventSourceEvent
    roles = ["DATASET_READ"]

    def _poll_job_info(self, dataset_name: str) -> dict[str, typing.Any] | None:
        """Return a status entry for the given dataset's active job, or None if not found."""
        try:
            last = get_last_job(dataset_name)
        except KeyError:
            return None
        info = get_info(last.dataset_name, last.job_uuid)
        return _map_info_result(info)

    def run_sync(self) -> None:
        dataset_name = self.typed_arg.dataset_name
        last_info = None

        while not self._cancel_sync.is_set():
            try:
                current_info = self._poll_job_info(dataset_name)

                if current_info != last_info:
                    if current_info is not None:
                        self.send_event("CHANGED", fields=current_info)

                    last_info = current_info
            except Exception:
                pass

            self._cancel_sync.wait(2)


class ZfsTierRewriteJobQueryEventSource(
    TypedEventSource[ZfsTierRewriteJobQueryEventSourceArgs]
):
    """
    Subscribe to ZFS rewrite job collection events (ADDED, CHANGED, REMOVED).
    On subscribe, sends ADDED for all existing jobs, then polls every 5 seconds
    and fires CHANGED when a job transitions state or REMOVED when it disappears.
    """

    args = ZfsTierRewriteJobQueryEventSourceArgs
    event = ZfsTierRewriteJobQueryEventSourceEvent
    roles = ["DATASET_READ"]

    def run_sync(self) -> None:
        known: dict[str, str] = {}
        first = True

        while not self._cancel_sync.is_set():
            current: dict[str, str] = {}
            for job in enum_jobs():
                tier_job_id = f"{job.dataset_name}@{job.job_uuid}"
                current[tier_job_id] = job.status

            for tier_job_id, status in current.items():
                prev = known.get(tier_job_id)
                dataset_name, _, job_uuid = tier_job_id.partition("@")
                entry = {
                    "tier_job_id": tier_job_id,
                    "dataset_name": dataset_name,
                    "job_uuid": job_uuid,
                    "status": status,
                }
                if prev is None:
                    if not first or status in (
                        RewriteJobStatus.RUNNING,
                        RewriteJobStatus.QUEUED,
                    ):
                        self.send_event("ADDED", id=tier_job_id, fields=entry)
                elif prev != status:
                    self.send_event("CHANGED", id=tier_job_id, fields=entry)

            for tier_job_id in set(known) - set(current):
                self.send_event("REMOVED", id=tier_job_id)

            known = current
            first = False
            self._cancel_sync.wait(5)


class ZfsTierConfigPart(ConfigServicePart[ZfsTierEntry]):
    _datastore = "zfs.tier"
    _entry = ZfsTierEntry

    async def do_update(self, data: dict[str, typing.Any]) -> ZfsTierEntry:
        old = await self.config()
        new_data = {**old.model_dump(), **data}
        await self.middleware.call("datastore.update", self._datastore, new_data["id"], new_data)
        return await self.config()


class ZfsTierService(GenericConfigService[ZfsTierEntry]):
    class Config:
        namespace = "zfs.tier"
        cli_private = True
        role_prefix = "DATASET"
        entry = ZfsTierEntry
        generic = True
        event_sources = {
            "zfs.tier.rewrite_job_status": ZfsTierRewriteJobStatusEventSource,
            "zfs.tier.rewrite_job_query": ZfsTierRewriteJobQueryEventSource,
        }

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = ZfsTierConfigPart(self.context)

    @api_method(
        ZfsTierUpdateArgs,
        ZfsTierUpdateResult,
        roles=["DATASET_WRITE"],
        audit="ZFS tier config update",
    )
    async def do_update(self, data: dict[str, typing.Any]) -> ZfsTierEntry:
        if not feature_is_licensed():
            raise CallError("ZFS tiering requires a license.")

        old = await self.config()
        new = await self._svc_part.do_update(data)
        await self.middleware.call("etc.generate", "truenas_zfstierd")
        if new.enabled != old.enabled:
            verb = "START" if new.enabled else "STOP"
            await self.middleware.call("service.control", verb, "truenas_zfstierd")
        return new

    @api_method(
        ZfsTierRewriteJobCreateArgs,
        ZfsTierRewriteJobCreateResult,
        roles=["DATASET_WRITE"],
        audit="ZFS tier rewrite job create",
        audit_extended=lambda data: data["dataset_name"],
    )
    async def rewrite_job_create(self, data: dict[str, typing.Any]) -> dict[str, typing.Any]:
        """Create a new rewrite job for the specified ZFS dataset."""
        dataset_name = data["dataset_name"]
        field = "zfs_tier_rewrite_job_create.dataset_name"

        config = await self.config()
        if not config.enabled:
            raise ValidationError(
                field, "ZFS tiering is globally disabled", errno.EINVAL
            )

        tier_map = await self.call2(self.bulk_get_tier_info, [dataset_name])
        current_info = tier_map.get(dataset_name)
        if current_info is _DATASET_NOT_FOUND:
            raise ValidationError(
                field, f"{dataset_name!r}: dataset not found", errno.ENOENT
            )

        if current_info is None:
            raise ValidationError(
                field,
                f"{dataset_name!r}: tiering is not supported (pool has no SPECIAL vdev)",
                errno.EINVAL,
            )

        await self._validate_dataset_writable(dataset_name, field)

        space_info = await self.get_tier_space_info(dataset_name)
        if space_info is not None:
            self._validate_tier_space(
                field, dataset_name, current_info["tier_type"], space_info
            )

        async with RewriteClient() as client:
            try:
                result = await client.create_job(dataset_name)
            except RewriteClientException as e:
                _raise_client_error(e, field)

        return _map_create_result(result)

    @api_method(
        ZfsTierRewriteJobQueryArgs, ZfsTierRewriteJobQueryResult, roles=["DATASET_READ"]
    )
    async def rewrite_job_query(self, data: dict[str, typing.Any]) -> typing.Any:
        """Query rewrite jobs, optionally filtered by status."""
        status_filter = set(data.get("status") or [])
        jobs = []
        for job in enum_jobs():
            if status_filter and job.status not in status_filter:
                continue
            jobs.append(
                {
                    "tier_job_id": f"{job.dataset_name}@{job.job_uuid}",
                    "dataset_name": job.dataset_name,
                    "job_uuid": job.job_uuid,
                    "status": job.status,
                }
            )
        return filter_list(
            jobs, data.get("query-filters") or [], data.get("query-options") or {}
        )

    @api_method(
        ZfsTierRewriteJobStatusArgs,
        ZfsTierRewriteJobStatusResult,
        roles=["DATASET_READ"],
    )
    async def rewrite_job_status(self, data: dict[str, typing.Any]) -> dict[str, typing.Any]:
        """Get detailed status and statistics for a specific rewrite job."""
        dataset_name, job_uuid = self._parse_tier_job_id(data["tier_job_id"])
        try:
            info = get_info(dataset_name, job_uuid)
        except Exception as e:
            raise CallError(f"Failed to get job info: {e}")
        return _map_info_result(info)

    @api_method(
        ZfsTierRewriteJobFailuresArgs,
        ZfsTierRewriteJobFailuresResult,
        roles=["DATASET_READ"],
    )
    async def rewrite_job_failures(self, data: dict[str, typing.Any]) -> typing.Any:
        """List files that failed to be rewritten during a rewrite job."""
        dataset_name, job_uuid = self._parse_tier_job_id(data["tier_job_id"])
        try:
            resolved = get_resolved_failures(dataset_name, job_uuid)
        except Exception as e:
            raise CallError(f"Failed to get job failures: {e}")

        failures = []
        for f in resolved:
            failures.append(
                {
                    "filename": f.filename,
                    "error": {"errno": f.errno, "strerror": f.strerror},
                    "path": f.path,
                }
            )

        return filter_list(
            failures, data.get("query-filters") or [], data.get("query-options") or {}
        )

    @api_method(
        ZfsTierRewriteJobCancelArgs,
        ZfsTierRewriteJobCancelResult,
        roles=["DATASET_WRITE"],
        audit="ZFS tier rewrite job cancel",
        audit_extended=lambda data: data["tier_job_id"],
    )
    async def rewrite_job_cancel(self, data: dict[str, typing.Any]) -> None:
        """Cancel a running or queued rewrite job."""
        dataset_name, job_uuid = self._parse_tier_job_id(data["tier_job_id"])
        async with RewriteClient() as client:
            try:
                await client.abort_job(dataset_name, job_uuid)
            except RewriteClientException as e:
                _raise_client_error(e, "zfs_tier_rewrite_job_cancel.tier_job_id")

    @api_method(
        ZfsTierRewriteJobRecoverArgs,
        ZfsTierRewriteJobRecoverResult,
        roles=["DATASET_WRITE"],
        audit="ZFS tier rewrite job recover",
        audit_extended=lambda data: data["tier_job_id"],
    )
    async def rewrite_job_recover(self, data: dict[str, typing.Any]) -> dict[str, typing.Any]:
        """Recover a rewrite job in ERROR state by reissuing failed rewrites."""
        dataset_name, job_uuid = self._parse_tier_job_id(data["tier_job_id"])
        await self._validate_dataset_writable(
            dataset_name, "zfs_tier_rewrite_job_recover.tier_job_id"
        )
        async with RewriteClient() as client:
            try:
                result = await client.recover_job(dataset_name, job_uuid)
            except RewriteClientException as e:
                _raise_client_error(e, "zfs_tier_rewrite_job_recover.tier_job_id")

        return _map_recover_result(result)

    @private
    async def _validate_dataset_writable(self, dataset_name: str, field: str) -> None:
        """Raise ValidationError if the dataset is not mounted or is read-only."""
        results = await self.call2(
            self.s.zfs.resource.query_impl,
            ZFSResourceQuery(paths=[dataset_name], properties=["mounted", "readonly"]),
        )
        if not results:
            raise ValidationError(
                field, f"{dataset_name!r}: dataset not found", errno.ENOENT
            )

        props = results[0]["properties"]
        if props["mounted"]["raw"] == "no":
            raise ValidationError(
                field, f"{dataset_name!r}: dataset is not mounted", errno.EINVAL
            )

        if props["readonly"]["raw"] == "on":
            raise ValidationError(
                field, f"{dataset_name!r}: dataset is read-only", errno.EROFS
            )

    @private
    def _validate_tier_space(
        self, field: str, dataset_name: str, target_tier: str, space_info: dict[str, typing.Any]
    ) -> None:
        """Raise ValidationError if moving dataset_name to target_tier would exceed the space threshold."""
        dataset_used = space_info["dataset_used"]
        if target_tier == "PERFORMANCE":
            usable = space_info["class_special_usable"]
            if usable > 0:
                projected_pct = (
                    (space_info["class_special_used"] + dataset_used) / usable * 100
                )
                if projected_pct > 70:
                    raise ValidationError(
                        field,
                        f"{dataset_name!r}: moving this dataset to the PERFORMANCE tier would bring "
                        f"special vdev utilization to {projected_pct:.1f}%, exceeding the 70% warning "
                        f"threshold (80% is the cutoff at which ZFS stops writing to the PERFORMANCE tier)",
                        errno.ENOSPC,
                    )
        else:
            usable = space_info["class_normal_usable"]
            if usable > 0:
                projected_pct = (
                    (space_info["class_normal_used"] + dataset_used) / usable * 100
                )
                if projected_pct > 80:
                    raise ValidationError(
                        field,
                        f"{dataset_name!r}: moving this dataset to the REGULAR tier would bring "
                        f"normal class utilization to {projected_pct:.1f}%, exceeding the 80% threshold",
                        errno.ENOSPC,
                    )

    @private
    def _parse_tier_job_id(self, tier_job_id: str) -> tuple[str, str]:
        dataset_name, _, job_uuid = tier_job_id.partition("@")
        if not dataset_name or not job_uuid:
            raise CallError(f"Invalid tier_job_id: {tier_job_id!r}")
        return dataset_name, job_uuid

    @api_method(
        ZfsTierDatasetSetTierArgs,
        ZfsTierDatasetSetTierResult,
        roles=["DATASET_WRITE"],
        audit="ZFS tier dataset set tier",
        audit_extended=lambda data: f"{data['dataset_name']} -> {data['tier_type']}",
    )
    async def dataset_set_tier(self, data: dict[str, typing.Any]) -> dict[str, typing.Any]:
        """Set the performance tier for a ZFS dataset, optionally migrating existing data."""
        dataset_name = data["dataset_name"]
        tier_type = data["tier_type"]
        move_existing_data = data["move_existing_data"]
        field = "zfs_tier_dataset_set_tier.dataset_name"

        config = await self.config()
        if not config.enabled:
            raise ValidationError(
                "zfs_tier_dataset_set_tier", "ZFS tiering is globally disabled", errno.EINVAL
            )

        tier_map = await self.call2(self.bulk_get_tier_info, [dataset_name])
        current_info = tier_map.get(dataset_name)

        if current_info is _DATASET_NOT_FOUND:
            raise ValidationError(
                field, f"{dataset_name!r}: dataset not found", errno.ENOENT
            )

        if current_info is None:
            raise ValidationError(
                "zfs_tier_dataset_set_tier",
                f"{dataset_name!r}: tiering is not supported (pool has no SPECIAL vdev)",
                errno.EINVAL,
            )

        await self._validate_dataset_writable(dataset_name, field)

        tier_job = current_info.get("tier_job")
        if tier_job and tier_job["status"] in (
            RewriteJobStatus.RUNNING,
            RewriteJobStatus.QUEUED,
        ):
            raise ValidationError(
                field,
                f"{dataset_name!r}: a tier migration job is already in progress"
                f" (status: {tier_job['status']})",
                errno.EBUSY,
            )

        if tier_type != current_info["tier_type"]:
            space_info = await self.get_tier_space_info(dataset_name)
            if space_info is not None:
                self._validate_tier_space(field, dataset_name, tier_type, space_info)

        if tier_type == "PERFORMANCE":
            new_ssb = SPECIAL_SMALL_BLOCKS_PERFORMANCE
        else:
            new_ssb = SPECIAL_SMALL_BLOCKS_REGULAR

        await self.middleware.call(
            "pool.dataset.update_impl",
            UpdateImplArgs(name=dataset_name, zprops={"special_small_blocks": new_ssb}),
        )

        job_entry = None
        if move_existing_data:
            job_entry = await self.call2(
                self.rewrite_job_create, {"dataset_name": dataset_name}
            )

        new_tier_info = (await self.call2(self.bulk_get_tier_info, [dataset_name]))[
            dataset_name
        ]
        if job_entry is not None:
            new_tier_info = {**new_tier_info, "tier_job": job_entry}

        return typing.cast(dict[str, typing.Any], new_tier_info)

    @private
    async def get_tier_space_info(self, dataset_name: str) -> dict[str, typing.Any] | None:
        """
        Return special and normal class space info for the pool containing
        dataset_name, along with the dataset's current used bytes.

        Returns None if the info cannot be retrieved.
        """
        pool_name = dataset_name.split("/")[0]
        try:
            pools = await self.middleware.call(
                "zpool.query_impl",
                {
                    "pool_names": [pool_name],
                    "properties": [
                        "class_special_usable",
                        "class_special_used",
                        "class_normal_usable",
                        "class_normal_used",
                    ],
                },
            )
            if not pools:
                return None
            props = pools[0]["properties"]

            results = await self.call2(
                self.s.zfs.resource.query_impl,
                ZFSResourceQuery(paths=[dataset_name], properties=["used"]),
            )
            if not results:
                return None
        except Exception:
            return None

        try:
            return {
                "class_special_usable": props["class_special_usable"]["value"],
                "class_special_used": props["class_special_used"]["value"],
                "class_normal_usable": props["class_normal_usable"]["value"],
                "class_normal_used": props["class_normal_used"]["value"],
                "dataset_used": results[0]["properties"]["used"]["value"],
            }
        except (KeyError, TypeError, ValueError):
            return None

    @private
    @pass_thread_local_storage
    def bulk_get_tier_info(
        self, tls: typing.Any, dataset_names: list[str]
    ) -> dict[str, typing.Any]:
        """
        Efficiently returns {dataset_name: TierInfo|None} for multiple datasets.
        Checks license and enabled flag once; groups by pool for a single pool
        property check.
        """
        config = self.call_sync2(self.s.zfs.tier.config)
        if not config.enabled:
            return {ds: None for ds in dataset_names}

        return _bulk_tier_map(tls.lzh, dataset_names)
