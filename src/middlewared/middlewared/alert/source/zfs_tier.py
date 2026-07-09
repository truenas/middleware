from typing import Any

from truenas_zfstierd_client import enum_jobs, get_info
from truenas_zfstierd_common import RewriteJobStatus

from middlewared.alert.base import (
    Alert,
    AlertCategory,
    AlertClass,
    AlertLevel,
    OneShotAlertClass,
    ThreadedAlertSource,
)
from middlewared.plugins.zfs.tier import special_vdev_thresholds

_TERMINAL_STATUSES = (RewriteJobStatus.ERROR, RewriteJobStatus.COMPLETE)


class TierJobErrorAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False
    category = AlertCategory.TASKS
    level = AlertLevel.CRITICAL
    title = "Tier Migration Job Error"
    text = "Tier migration job %(tier_job_id)s encountered an error: %(error)s"

    async def create(self, args):
        return Alert(TierJobErrorAlertClass, args, key=args["tier_job_id"])

    async def delete(self, alerts, query):
        return list(filter(lambda alert: alert.key != str(query), alerts))


class TierJobCompleteAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False
    category = AlertCategory.TASKS
    level = AlertLevel.NOTICE
    title = "Tier Migration Job Complete"
    text = (
        "Tier migration job %(tier_job_id)s completed successfully. %(files)s files "
        "migrated to %(tier)s for a total of %(size)s bytes of data."
    )

    async def create(self, args):
        return Alert(TierJobCompleteAlertClass, args, key=args["tier_job_id"])

    async def delete(self, alerts, query):
        return list(filter(lambda alert: alert.key != str(query), alerts))


class TierSpecialVdevCriticalAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False
    category = AlertCategory.STORAGE
    level = AlertLevel.CRITICAL
    title = "Special Allocation Class Space Critical"
    text = (
        "Pool %(pool_name)s: special allocation class usage exceeds "
        "%(threshold)d%%. Tier rewrites will abort and PERFORMANCE-tier "
        "writes may overflow into the REGULAR tier."
    )

    async def create(self, args):
        return Alert(TierSpecialVdevCriticalAlertClass, args, key=args["pool_name"])

    async def delete(self, alerts, query):
        return list(filter(lambda alert: alert.key != str(query), alerts))


class TierSpecialVdevWarningAlertClass(AlertClass, OneShotAlertClass):
    deleted_automatically = False
    category = AlertCategory.STORAGE
    level = AlertLevel.WARNING
    title = "Special Allocation Class Space Warning"
    text = (
        "Pool %(pool_name)s: special allocation class usage exceeds "
        "%(threshold)d%% — within 10 points of the configured critical cap."
    )

    async def create(self, args):
        return Alert(TierSpecialVdevWarningAlertClass, args, key=args["pool_name"])

    async def delete(self, alerts, query):
        return list(filter(lambda alert: alert.key != str(query), alerts))


class TierJobAlertSource(ThreadedAlertSource):
    """Single threaded source that drives every Tier* OneShot alert.

    Gated at runtime on ``zfs.tier.config.enabled`` — community and
    licensed-but-disabled boxes both early-exit. The two job alerts
    (ERROR / COMPLETE) are fired once per terminal-state UUID, tracked
    in memory so dismissal sticks across polls; the two SPECIAL-vdev
    alerts are fired/cleared every poll based on the current
    ``class_special_used / class_special_usable`` ratio per pool.
    """

    def __init__(self, middleware: Any) -> None:
        super().__init__(middleware)
        self._fired_terminal_jobs: set[str] = set()
        self._fired_special_pools: set[str] = set()

    def check_sync(self) -> list:
        try:
            config = self.middleware.call_sync("zfs.tier.config")
        except Exception:
            self.middleware.logger.warning("Failed to read zfs.tier.config", exc_info=True)
            return []

        if not config.enabled:
            self._clear_all_oneshots()
            return []

        warning_pct, critical_pct = special_vdev_thresholds(config)

        try:
            self._check_jobs()
        except Exception:
            self.middleware.logger.warning("Failed to check tier job alerts", exc_info=True)

        try:
            self._check_special_vdev_usage(warning_pct, critical_pct)
        except Exception:
            self.middleware.logger.warning("Failed to check special vdev space alerts", exc_info=True)

        return []

    # ------------------------------------------------------------------
    # Job ERROR/COMPLETE OneShots
    # ------------------------------------------------------------------

    def _check_jobs(self) -> None:
        current_terminal: set[str] = set()

        # Materialize first: enum_jobs() holds an LMDB read transaction open for
        # the life of the iterator, and _fire_job_alert() -> get_info() below opens
        # another read transaction on the same thread. LMDB permits one read
        # transaction per thread, so reading inside the live iterator raises
        # MDB_BAD_RSLOT.
        for job in list(enum_jobs()):
            tier_job_id = f"{job.dataset_name}@{job.job_uuid}"

            if job.status in _TERMINAL_STATUSES:
                current_terminal.add(tier_job_id)
                if tier_job_id in self._fired_terminal_jobs:
                    continue
                self._fire_job_alert(job, tier_job_id)
                self._fired_terminal_jobs.add(tier_job_id)
            else:
                if tier_job_id in self._fired_terminal_jobs:
                    self.middleware.call_sync(
                        "alert.oneshot_delete",
                        "TierJobError",
                        tier_job_id,
                    )
                    self.middleware.call_sync(
                        "alert.oneshot_delete",
                        "TierJobComplete",
                        tier_job_id,
                    )
                    self._fired_terminal_jobs.discard(tier_job_id)

        self._fired_terminal_jobs &= current_terminal

    def _fire_job_alert(self, job: Any, tier_job_id: str) -> None:
        if job.status == RewriteJobStatus.ERROR:
            try:
                info = get_info(job.dataset_name, job.job_uuid)
                error = info.error or ""
            except Exception:
                self.middleware.logger.debug(
                    "Failed to get info for tier job %s",
                    tier_job_id,
                    exc_info=True,
                )
                error = ""
            self.middleware.call_sync(
                "alert.oneshot_create",
                "TierJobError",
                {"tier_job_id": tier_job_id, "error": error},
            )
            return

        try:
            info = get_info(job.dataset_name, job.job_uuid)
            stats = info.stats
        except Exception:
            self.middleware.logger.debug(
                "Failed to get info for tier job %s",
                tier_job_id,
                exc_info=True,
            )
            stats = None

        tier_map = self.middleware.call_sync(
            "zfs.tier.bulk_get_tier_info",
            [job.dataset_name],
        )
        tier_info = tier_map.get(job.dataset_name)
        if not tier_info:
            return

        self.middleware.call_sync(
            "alert.oneshot_create",
            "TierJobComplete",
            {
                "tier_job_id": tier_job_id,
                "files": stats.success if stats else 0,
                "tier": tier_info["tier_type"],
                "size": str(stats.count_bytes if stats else 0),
            },
        )

    # ------------------------------------------------------------------
    # SPECIAL-vdev space OneShots
    # ------------------------------------------------------------------

    def _check_special_vdev_usage(self, warning_pct: int, critical_pct: int) -> None:
        pools = self.middleware.call_sync(
            "zpool.query_impl",
            {"properties": ["class_special_usable", "class_special_used"]},
        )

        current_pools: set[str] = set()
        for pool in pools:
            props = pool.get("properties") or {}
            usable_prop = props.get("class_special_usable") or {}
            used_prop = props.get("class_special_used") or {}
            usable = usable_prop.get("value") if isinstance(usable_prop, dict) else None
            used = used_prop.get("value") if isinstance(used_prop, dict) else None

            if not usable or used is None:
                continue

            pool_name = pool.get("name")
            if not pool_name:
                continue

            current_pools.add(pool_name)
            pct = (used / usable) * 100

            if pct > critical_pct:
                self.middleware.call_sync(
                    "alert.oneshot_create",
                    "TierSpecialVdevCritical",
                    {"pool_name": pool_name, "threshold": critical_pct},
                )
                self.middleware.call_sync(
                    "alert.oneshot_delete",
                    "TierSpecialVdevWarning",
                    pool_name,
                )
            elif pct > warning_pct:
                self.middleware.call_sync(
                    "alert.oneshot_create",
                    "TierSpecialVdevWarning",
                    {"pool_name": pool_name, "threshold": warning_pct},
                )
                self.middleware.call_sync(
                    "alert.oneshot_delete",
                    "TierSpecialVdevCritical",
                    pool_name,
                )
            else:
                self.middleware.call_sync(
                    "alert.oneshot_delete",
                    "TierSpecialVdevWarning",
                    pool_name,
                )
                self.middleware.call_sync(
                    "alert.oneshot_delete",
                    "TierSpecialVdevCritical",
                    pool_name,
                )

        for stale in self._fired_special_pools - current_pools:
            self.middleware.call_sync(
                "alert.oneshot_delete",
                "TierSpecialVdevWarning",
                stale,
            )
            self.middleware.call_sync(
                "alert.oneshot_delete",
                "TierSpecialVdevCritical",
                stale,
            )
        self._fired_special_pools = current_pools

    def _clear_all_oneshots(self) -> None:
        for pool_name in self._fired_special_pools:
            try:
                self.middleware.call_sync(
                    "alert.oneshot_delete",
                    "TierSpecialVdevWarning",
                    pool_name,
                )
                self.middleware.call_sync(
                    "alert.oneshot_delete",
                    "TierSpecialVdevCritical",
                    pool_name,
                )
            except Exception:
                pass
        self._fired_special_pools.clear()

        for tier_job_id in self._fired_terminal_jobs:
            try:
                self.middleware.call_sync(
                    "alert.oneshot_delete",
                    "TierJobError",
                    tier_job_id,
                )
                self.middleware.call_sync(
                    "alert.oneshot_delete",
                    "TierJobComplete",
                    tier_job_id,
                )
            except Exception:
                pass
        self._fired_terminal_jobs.clear()
