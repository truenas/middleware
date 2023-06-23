from datetime import timedelta

from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, AlertSource, Alert
from middlewared.alert.schedule import IntervalSchedule


class EncryptedDatasetAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = 'Unencrypted datasets detected within encrypted datasets'
    text = (
        'The following datasets are not encrypted but are within an encrypted dataset: %(datasets)r which is '
        'not supported behaviour and may lead to various issues.'
    )


class UnencryptedDatasetsAlertSource(AlertSource):

    schedule = IntervalSchedule(timedelta(hours=12))

    async def check(self):
        unencrypted_datasets = []
        for dataset in await self.middleware.call('pool.dataset.query', [['encrypted', '=', True]]):
            for child in dataset['children']:
                if child['name'] == f'{child["pool"]}/ix-applications' or child['name'].startswith(
                    f'{child["pool"]}/ix-applications/'
                ):
                    continue

                if not child['encrypted']:
                    unencrypted_datasets.append(child['name'])

        if unencrypted_datasets:
            return Alert(EncryptedDatasetAlertClass, {'datasets': ', '.join(unencrypted_datasets)})
