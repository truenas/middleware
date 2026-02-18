from dataclasses import dataclass
from typing import Any

import truenas_zfsrewrited
from truenas_zfsrewrited_common import RewriteJobStatus

from middlewared.alert.base import (
    Alert, AlertCategory, AlertClassConfig, AlertClass, AlertLevel,
    NonDataclassAlertClass, OneShotAlertClass, ThreadedAlertSource,
)


@dataclass(kw_only=True)
class TierJobErrorAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.TASKS,
        level=AlertLevel.CRITICAL,
        title='Tier Migration Job Error',
        text='Tier migration job %(tier_job_id)s encountered an error: %(error)s',
    )

    tier_job_id: str
    error: str

    @classmethod
    def key_from_args(cls, args: Any) -> Any:
        return args['tier_job_id']


@dataclass(kw_only=True)
class TierJobCompleteAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.TASKS,
        level=AlertLevel.NOTICE,
        title='Tier Migration Job Complete',
        text=(
            'Tier migration job %(tier_job_id)s completed successfully. %(files)s files '
            'migrated to %(tier)s for a total of %(size)s bytes of data.'
        ),
    )

    tier_job_id: str
    files: int
    tier: str
    size: str

    @classmethod
    def key_from_args(cls, args: Any) -> Any:
        return args['tier_job_id']


class TierSpecialVdevCriticalAlert(NonDataclassAlertClass[str], OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.STORAGE,
        level=AlertLevel.CRITICAL,
        title='Special Allocation Class Space Critical',
        text=(
            'Used space in special allocation class exceeds 80%%. Further data writes '
            'to PERFORMANCE tier will overflow into REGULAR tier.'
        ),
    )


class TierSpecialVdevWarningAlert(NonDataclassAlertClass[str], OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.STORAGE,
        level=AlertLevel.WARNING,
        title='Special Allocation Class Space Warning',
        text=(
            'Used space in special allocation class exceeds 70%%. Once the 80%% used '
            'threshold is exceeded further data writes to the PERFORMANCE tier will '
            'overflow into the REGULAR tier.'
        ),
    )


class TierJobAlertSource(ThreadedAlertSource):
    def check_sync(self) -> list[Alert[Any]]:
        alerts = []

        try:
            for job in truenas_zfsrewrited.iter_jobs():
                tier_job_id = f'{job.dataset_name}@{job.uuid}'

                if job.state == RewriteJobStatus.ERROR:
                    try:
                        jinfo = truenas_zfsrewrited.get_job_info(job.dataset_name, job.uuid)
                        error = jinfo.error or ''
                    except Exception:
                        error = ''
                    alerts.append(Alert(TierJobErrorAlert(tier_job_id=tier_job_id, error=error)))

                elif job.state == RewriteJobStatus.COMPLETE:
                    try:
                        jinfo = truenas_zfsrewrited.get_job_info(job.dataset_name, job.uuid)
                        stats = jinfo.stats
                    except Exception:
                        stats = None

                    tier_map = self.middleware.call_sync('zfs.tier.bulk_get_tier_info', [job.dataset_name])
                    tier_info = tier_map.get(job.dataset_name)
                    if tier_info:
                        alerts.append(Alert(TierJobCompleteAlert(
                            tier_job_id=tier_job_id,
                            files=stats.success if stats else 0,
                            tier=tier_info['tier_type'],
                            size=str(stats.count_bytes if stats else 0),
                        )))
        except Exception:
            pass

        return alerts
