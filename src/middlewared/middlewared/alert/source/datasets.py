from middlewared.alert.base import AlertClass, AlertCategory, AlertLevel, AlertSource, Alert


class EncryptedDatasetAlertClass(AlertClass):
    category = AlertCategory.SYSTEM
    level = AlertLevel.WARNING
    title = 'Unencrypted datasets detected within encrypted datasets'
    text = (
        'The following datasets are not encrypted but are within an encrypted dataset: %(datasets)r which is '
        'not supported behaviour and may lead to various issues.'
    )


class UnencryptedDatasetsAlertSource(AlertSource):

    async def check(self):
        unencrypted_datasets = []
        for dataset in await self.middleware.call('pool.dataset.query', [['encrypted', '=', True]]):
            for child in dataset['children']:
                if not child['encrypted']:
                    unencrypted_datasets.append(child['name'])

        if unencrypted_datasets:
            return Alert(EncryptedDatasetAlertClass, {'datasets': ', '.join(unencrypted_datasets)})
