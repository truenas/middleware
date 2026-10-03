from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from middlewared.alert.base import Alert, AlertCategory, AlertClass, AlertClassConfig, AlertLevel, AlertSource
from middlewared.alert.schedule import IntervalSchedule
from middlewared.api.current import ZFSResourceQuery


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
        encrypted, unencrypted = set(), []
        for ds in await self.call2(
            self.s.zfs.resource.list_impl, ZFSResourceQuery(properties=['encryption'], get_children=True)
        ):
            if ds['properties']['encryption']['raw'] != 'off':
                encrypted.add(ds['name'])
            elif ds['name'].rsplit('/', 1)[0] in encrypted:
                unencrypted.append(ds['name'])

        if unencrypted:
            return Alert(EncryptedDatasetAlert(datasets=', '.join(unencrypted)))

        return None
