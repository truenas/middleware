from unittest.mock import Mock

import pytest

from middlewared.alert.base import Alert
from middlewared.alert.source.quota import QuotaCriticalAlertClass, QuotaAlertSource
from middlewared.plugins.zfs_.utils import TNUserProp

DEFAULT_QUOTA_THRESHOLDS = {k: v for k, v in TNUserProp.quotas()}
FAUX_POOL = "tank"
FAUX_POOL_TOTAL = 9881780224
FAUX_DS = f"{FAUX_POOL}/share/HR"


@pytest.mark.parametrize("dataset_query,alerts", [
    (
        {
            "pools": {FAUX_POOL: FAUX_POOL_TOTAL},
            "datasets": {
                FAUX_DS: {
                    "pool": FAUX_POOL,
                    "properties": {
                        "used": {"value": 10485760},
                        "quota": {"value": 10485760},
                        "refquota": {"value": 0},
                        "available": {"value": 10395648},
                    },
                    "user_properties": DEFAULT_QUOTA_THRESHOLDS
                }
            }
        },
        []
    ),
    (
        {
            "pools": {FAUX_POOL: FAUX_POOL_TOTAL},
            "datasets": {
                FAUX_DS: {
                    "pool": FAUX_POOL,
                    "properties": {
                        "usedbydataset": {"value": 10000000},
                        "refquota": {"value": 10485760},
                        "quota": {"value": 0},
                    },
                    "user_properties": DEFAULT_QUOTA_THRESHOLDS
                }
            }
        },
        [
            Alert(
                QuotaCriticalAlertClass,
                args={
                    "name": "Refquota",
                    "dataset": FAUX_DS,
                    "used_fraction": 95.367431640625,
                    "used": "9.54 MiB",
                    "quota_value": "10 MiB",
                },
                key=[FAUX_DS, "refquota"],
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
