from dataclasses import dataclass
from typing import Any

from truenas_zfstierd_client import enum_jobs, get_info
from truenas_zfstierd_common import RewriteJobStatus

from middlewared.alert.base import (
    Alert,
    AlertCategory,
    AlertClassConfig,
    AlertLevel,
    OneShotAlertClass,
    ThreadedAlertSource,
)
from middlewared.plugins.zfs.tier import special_vdev_thresholds

_TERMINAL_STATUSES = (RewriteJobStatus.ERROR, RewriteJobStatus.COMPLETE)


@dataclass(kw_only=True)
class TierJobErrorAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.TASKS,
        level=AlertLevel.CRITICAL,
        title="Tier Migration Job Error",
        text="Tier migration job %(tier_job_id)s encountered an error: %(error)s",
    )

    tier_job_id: str
    error: str

    @classmethod
    def key_from_args(cls, args: Any) -> Any:
        return args["tier_job_id"]


@dataclass(kw_only=True)
class TierJobCompleteAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.TASKS,
        level=AlertLevel.NOTICE,
        title="Tier Migration Job Complete",
        text=(
            "Tier migration job %(tier_job_id)s completed successfully. %(files)s files "
            "migrated to %(tier)s for a total of %(size)s bytes of data."
        ),
    )

    tier_job_id: str
    files: int
    tier: str
    size: str

    @classmethod
    def key_from_args(cls, args: Any) -> Any:
        return args["tier_job_id"]


@dataclass(kw_only=True)
class TierSpecialVdevCriticalAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.STORAGE,
        level=AlertLevel.CRITICAL,
        title="Special Allocation Class Space Critical",
        text=(
            "Pool %(pool_name)s: special allocation class usage exceeds "
            "%(threshold)d%%. Tier rewrites will abort and PERFORMANCE-tier "
            "writes may overflow into the REGULAR tier."
        ),
    )

    pool_name: str
    threshold: int

    @classmethod
    def key_from_args(cls, args: Any) -> Any:
        return args["pool_name"]


@dataclass(kw_only=True)
class TierSpecialVdevWarningAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.STORAGE,
        level=AlertLevel.WARNING,
        title="Special Allocation Class Space Warning",
        text=(
            "Pool %(pool_name)s: special allocation class usage exceeds "
            "%(threshold)d%% — within 10 points of the configured critical cap."
        ),
    )

    pool_name: str
    threshold: int

    @classmethod
    def key_from_args(cls, args: Any) -> Any:
        return args["pool_name"]


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

    def check_sync(self) -> list[Alert[Any]]:
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

        for job in enum_jobs():
            tier_job_id = f"{job.dataset_name}@{job.job_uuid}"

            if job.status in _TERMINAL_STATUSES:
                current_terminal.add(tier_job_id)
                if tier_job_id in self._fired_terminal_jobs:
                    continue
                self._fire_job_alert(job, tier_job_id)
                self._fired_terminal_jobs.add(tier_job_id)
            else:
                # Job moved out of a terminal state (e.g., recover from ERROR);
                # drop the alert so it doesn't linger past the fix.
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

        # Jobs that disappeared entirely (e.g., LMDB pruned) — drop our memo.
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
                TierJobErrorAlert(tier_job_id=tier_job_id, error=error),
            )
            return

        # COMPLETE
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
            TierJobCompleteAlert(
                tier_job_id=tier_job_id,
                files=stats.success if stats else 0,
                tier=tier_info["tier_type"],
                size=str(stats.count_bytes if stats else 0),
            ),
        )

    # ------------------------------------------------------------------
    # SPECIAL-vdev space OneShots
    # ------------------------------------------------------------------

    def _check_special_vdev_usage(self, warning_pct: int, critical_pct: int) -> None:
        pools = self.middleware.call_sync(
            "zpool.query_impl",
            {
                "properties": [
                    "class_special_usable",
                    "class_special_used",
                ],
            },
        )

        current_pools: set[str] = set()
        for pool in pools:
            props = pool.get("properties") or {}
            usable_prop = props.get("class_special_usable") or {}
            used_prop = props.get("class_special_used") or {}
            usable = usable_prop.get("value") if isinstance(usable_prop, dict) else None
            used = used_prop.get("value") if isinstance(used_prop, dict) else None

            if not usable or used is None:
                # Pool has no SPECIAL vdev — skip.
                continue

            pool_name = pool.get("name")
            if not pool_name:
                continue

            current_pools.add(pool_name)
            pct = (used / usable) * 100

            if pct > critical_pct:
                self.middleware.call_sync(
                    "alert.oneshot_create",
                    TierSpecialVdevCriticalAlert(pool_name=pool_name, threshold=critical_pct),
                )
                self.middleware.call_sync(
                    "alert.oneshot_delete",
                    "TierSpecialVdevWarning",
                    pool_name,
                )
            elif pct > warning_pct:
                self.middleware.call_sync(
                    "alert.oneshot_create",
                    TierSpecialVdevWarningAlert(pool_name=pool_name, threshold=warning_pct),
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

        # Pools that vanished since the last poll (export/destroy) — clear
        # any alerts we'd previously raised for them.
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

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def _clear_all_oneshots(self) -> None:
        """Drop every Tier* alert we've raised. Used when tiering flips
        from enabled → disabled so stale state doesn't outlive the
        feature."""
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
