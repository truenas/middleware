from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from middlewared.alert.base import Alert, AlertCategory, AlertClass, AlertClassConfig, AlertLevel, AlertSource
from middlewared.alert.schedule import IntervalSchedule


@dataclass(kw_only=True)
class EncryptedDatasetAlert(AlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SYSTEM,
        level=AlertLevel.WARNING,
        title="Unencrypted datasets detected within encrypted datasets",
        text=(
            "The following datasets are not encrypted but are within an encrypted dataset: %(datasets)r which is "
            "not supported behaviour and may lead to various issues."
        ),
    )

    datasets: str


class UnencryptedDatasetsAlertSource(AlertSource):

    schedule = IntervalSchedule(timedelta(hours=12))

    async def check(self) -> list[Alert[Any]] | Alert[Any] | None:
        unencrypted_datasets = []
        for dataset in await self.middleware.call("pool.dataset.query", [["encrypted", "=", True]]):
            for child in dataset["children"]:
                if child["name"] in (
                    f'{child["pool"]}/ix-applications', f'{child["pool"]}/ix-apps'
                ) or child["name"].startswith((
                    f'{child["pool"]}/ix-applications/', f'{child["pool"]}/ix-apps/'
                )):
                    continue

                if not child["encrypted"]:
                    unencrypted_datasets.append(child["name"])

        if unencrypted_datasets:
            return Alert(EncryptedDatasetAlert(datasets=", ".join(unencrypted_datasets)))

        return None
