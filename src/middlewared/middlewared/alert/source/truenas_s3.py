from dataclasses import dataclass
from typing import Any

from middlewared.alert.base import AlertCategory, AlertClassConfig, AlertLevel, OneShotAlertClass


@dataclass(kw_only=True)
class S3BucketDatasetMissingAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SHARING,
        level=AlertLevel.WARNING,
        title="S3 Bucket Dataset Is Missing",
        text=(
            'S3 bucket "%(name)s" is unavailable because its dataset %(dataset)s no longer exists. Restore the '
            "dataset, or delete and recreate the bucket."
        ),
        deleted_automatically=False,
    )

    id: int
    name: str
    dataset: str

    @classmethod
    def key_from_args(cls, args: Any) -> Any:
        # one alert per bucket, cleared by its id
        return args["id"]
