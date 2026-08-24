from typing import Any

from truenas_zfstierd_client import enum_jobs, get_info
from truenas_zfstierd_common import RewriteJobStatus

from middlewared.alert.base import (
    Alert,
    AlertCategory,
    AlertClass,
    AlertLevel,
    ThreadedAlertSource,
)
from middlewared.plugins.zfs.tier import special_vdev_thresholds


class TierJobErrorAlertClass(AlertClass):
    category = AlertCategory.TASKS
    level = AlertLevel.CRITICAL
    title = "Tier Migration Job Error"
    text = "Tier migration job %(tier_job_id)s encountered an error: %(error)s"


class TierJobCompleteAlertClass(AlertClass):
    category = AlertCategory.TASKS
    level = AlertLevel.NOTICE
    title = "Tier Migration Job Complete"
    text = (
        "Tier migration job %(tier_job_id)s completed successfully. %(files)s files "
        "migrated to %(tier)s for a total of %(size)s bytes of data."
    )


class TierSpecialVdevCriticalAlertClass(AlertClass):
    category = AlertCategory.STORAGE
    level = AlertLevel.CRITICAL
    title = "Special Allocation Class Space Critical"
    text = (
        "Pool %(pool_name)s: special allocation class usage exceeds "
        "%(threshold)d%%. Tier rewrites will abort and PERFORMANCE-tier "
        "writes may overflow into the REGULAR tier."
    )


class TierSpecialVdevWarningAlertClass(AlertClass):
    category = AlertCategory.STORAGE
    level = AlertLevel.WARNING
    title = "Special Allocation Class Space Warning"
    text = (
        "Pool %(pool_name)s: special allocation class usage exceeds "
        "%(threshold)d%% — within 10 points of the configured critical cap."
    )


# Sorted (dataset_name, job_uuid) pairs of the ERROR and COMPLETE jobs seen on
# a poll — identifies the job set a cached computation belongs to.
_JobAlertsCacheKey = tuple[tuple[tuple[str, str], ...], tuple[tuple[str, str], ...]]


class _JobAlertsCache:
    """Single-slot memo of the alerts computed for a set of terminal jobs.

    ``get_info()`` and ``bulk_get_tier_info()`` results are stable for a
    given terminal job, so the previous poll's alerts can be reused while
    the set of terminal jobs is unchanged. Re-serving the same ``Alert``
    instances is safe: the framework re-derives their bookkeeping fields
    (uuid, datetime, dismissed, node) per poll, keyed by alert class and
    alert key.
    """

    def __init__(self) -> None:
        self._key: _JobAlertsCacheKey | None = None
        self._alerts: list[Alert] = []

    @staticmethod
    def _key_for(error_jobs: list[Any], complete_jobs: list[Any]) -> _JobAlertsCacheKey:
        return (
            tuple(sorted((job.dataset_name, job.job_uuid) for job in error_jobs)),
            tuple(sorted((job.dataset_name, job.job_uuid) for job in complete_jobs)),
        )

    def get(self, error_jobs: list[Any], complete_jobs: list[Any]) -> list[Alert] | None:
        """Return the alerts cached for this job set, or ``None`` on miss."""
        if self._key != self._key_for(error_jobs, complete_jobs):
            return None
        return list(self._alerts)

    def store(self, error_jobs: list[Any], complete_jobs: list[Any], alerts: list[Alert]) -> None:
        self._key = self._key_for(error_jobs, complete_jobs)
        self._alerts = list(alerts)

    def clear(self) -> None:
        self._key = None
        self._alerts = []


class TierJobAlertSource(ThreadedAlertSource):
    """Single threaded source that drives every Tier* alert.

    Gated at runtime on ``zfs.tier.config.enabled`` — community and
    licensed-but-disabled boxes both return no alerts, which clears any
    previously raised ones. The two job alerts (ERROR / COMPLETE) exist
    for as long as the corresponding job record sits in that terminal
    state; the two SPECIAL-vdev alerts reflect the current
    ``class_special_used / class_special_usable`` ratio per pool. All
    lifecycle management (dedup by key, dismissal, clearing) is handled
    by the alert framework.
    """

    run_on_backup_node = False

    def __init__(self, middleware: Any) -> None:
        super().__init__(middleware)
        self._job_alerts_cache = _JobAlertsCache()

    def check_sync(self) -> list[Alert]:
        config = self.call_sync2(self.s.zfs.tier.config)
        if not config.enabled:
            # Drop the cache: tier info baked into cached COMPLETE alerts
            # (e.g. tier_type) may change while tiering is disabled.
            self._job_alerts_cache.clear()
            return []

        warning_pct, critical_pct = special_vdev_thresholds(config)
        return self._check_jobs() + self._check_special_vdev_usage(warning_pct, critical_pct)

    def _check_jobs(self) -> list[Alert]:
        error_jobs = []
        complete_jobs = []

        # Materialize first: enum_jobs() holds an LMDB read transaction open for
        # the life of the iterator, and get_info() below opens another read
        # transaction on the same thread. LMDB permits one read transaction per
        # thread, so reading inside the live iterator raises MDB_BAD_RSLOT.
        for job in list(enum_jobs()):
            if job.status == RewriteJobStatus.ERROR:
                error_jobs.append(job)
            elif job.status == RewriteJobStatus.COMPLETE:
                complete_jobs.append(job)

        cached = self._job_alerts_cache.get(error_jobs, complete_jobs)
        if cached is not None:
            return cached

        alerts: list[Alert] = []

        for job in error_jobs:
            tier_job_id = f"{job.dataset_name}@{job.job_uuid}"
            try:
                error = get_info(job.dataset_name, job.job_uuid).error or ""
            except Exception:
                self.middleware.logger.debug(
                    "Failed to get info for tier job %s",
                    tier_job_id,
                    exc_info=True,
                )
                error = ""
            alerts.append(Alert(
                TierJobErrorAlertClass,
                {"tier_job_id": tier_job_id, "error": error},
                key=tier_job_id,
            ))

        if complete_jobs:
            tier_map = self.call_sync2(
                self.s.zfs.tier.bulk_get_tier_info,
                [job.dataset_name for job in complete_jobs],
            )
            for job in complete_jobs:
                tier_info = tier_map.get(job.dataset_name)
                if not tier_info:
                    continue

                tier_job_id = f"{job.dataset_name}@{job.job_uuid}"
                try:
                    stats = get_info(job.dataset_name, job.job_uuid).stats
                except Exception:
                    self.middleware.logger.debug(
                        "Failed to get info for tier job %s",
                        tier_job_id,
                        exc_info=True,
                    )
                    stats = None

                alerts.append(Alert(
                    TierJobCompleteAlertClass,
                    {
                        "tier_job_id": tier_job_id,
                        "files": stats.success if stats else 0,
                        "tier": tier_info["tier_type"],
                        "size": str(stats.count_bytes if stats else 0),
                    },
                    key=tier_job_id,
                ))

        self._job_alerts_cache.store(error_jobs, complete_jobs, alerts)
        return alerts

    def _check_special_vdev_usage(self, warning_pct: int, critical_pct: int) -> list[Alert]:
        pools = self.middleware.call_sync(
            "zpool.query_impl",
            {"properties": ["class_special_usable", "class_special_used"]},
        )

        alerts: list[Alert] = []
        for pool in pools:
            props = pool.get("properties") or {}
            usable_prop = props.get("class_special_usable") or {}
            used_prop = props.get("class_special_used") or {}
            usable = usable_prop.get("value") if isinstance(usable_prop, dict) else None
            used = used_prop.get("value") if isinstance(used_prop, dict) else None

            if not usable or used is None:
                # Pool has no SPECIAL vdev — skip.
                continue

            pool_name = pool["name"]
            pct = (used / usable) * 100

            if pct > critical_pct:
                alerts.append(Alert(
                    TierSpecialVdevCriticalAlertClass,
                    {"pool_name": pool_name, "threshold": critical_pct},
                    key=pool_name,
                ))
            elif pct > warning_pct:
                alerts.append(Alert(
                    TierSpecialVdevWarningAlertClass,
                    {"pool_name": pool_name, "threshold": warning_pct},
                    key=pool_name,
                ))

        return alerts
