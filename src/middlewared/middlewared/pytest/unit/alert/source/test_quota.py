from unittest.mock import Mock

import pytest

from middlewared.alert.base import Alert
from middlewared.alert.source.quota import QuotaCriticalAlertClass, QuotaAlertSource


@pytest.mark.parametrize("dataset_query,alerts", [
    # 10 MB quota, 10 MB reserved, a few kilobytes used
    (
        [
            {
                "name": {"rawvalue": "Volume_1/Hard_Drives/Bill_HDD"},
                "used": {"rawvalue": "10485760"},
                "quota": {"rawvalue": "10485760"},
                "available": {"rawvalue": "10395648"},
            },
        ],
        []
    ),
    # Refquota
    (
        [
            {
                "name": {"rawvalue": "Volume_1/Hard_Drives/Bill_HDD"},
                "usedbydataset": {"rawvalue": "10000000"},
                "refquota": {"rawvalue": "10485760"},
            },
        ],
        [
            Alert(
                QuotaCriticalAlertClass,
                args={
                    "name": "Refquota",
                    "dataset": "Volume_1/Hard_Drives/Bill_HDD",
                    "used_fraction": 95.367431640625,
                    "used": "9.54 MiB",
                    "quota_value": "10 MiB",
                },
                key=["Volume_1/Hard_Drives/Bill_HDD", "refquota"],
                mail=None,
            )
        ]
    )
])
def test__quota_alert_source(dataset_query, alerts):
    middleware = Mock()
    middleware.call_sync.return_value = dataset_query

    qas = QuotaAlertSource(middleware)
    qas._get_owner = Mock(return_value=0)

    assert qas.check_sync() == alerts
