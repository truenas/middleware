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
        title='Unencrypted datasets detected within encrypted datasets',
        text=(
            'The following datasets are not encrypted but are within an encrypted dataset: %(datasets)r which is '
            'not supported behaviour and may lead to various issues.'
        ),
    )

    datasets: str


class UnencryptedDatasetsAlertSource(AlertSource):

    schedule = IntervalSchedule(timedelta(hours=12))

    async def check(self) -> list[Alert[Any]] | Alert[Any] | None:
        unencrypted_datasets = []
        for dataset in await self.middleware.call('pool.dataset.query', [['encrypted', '=', True]]):
            # No apps-dataset skip is needed here: pool.dataset.query already omits the datasets
            # middleware manages, and it never descends into one, so no child can be under them.
            for child in dataset['children']:
                if not child['encrypted']:
                    unencrypted_datasets.append(child['name'])

        if unencrypted_datasets:
            return Alert(EncryptedDatasetAlert(datasets=', '.join(unencrypted_datasets)))

        return None
