from unittest.mock import Mock

import pytest

from middlewared.alert.base import Alert
from middlewared.alert.source import quota
from middlewared.alert.source.quota import QuotaAlertSource, QuotaCriticalAlert

FAUX_POOL = "tank"
FAUX_DS = f"{FAUX_POOL}/share/HR"
DEFAULT_THRESHOLDS = {
    "quota_warning": "80",
    "quota_critical": "95",
    "refquota_warning": "80",
    "refquota_critical": "95",
}
REFQUOTA_CRITICAL = Alert(
    QuotaCriticalAlert(
        name="Refquota",
        dataset=FAUX_DS,
        used_fraction=95.367431640625,
        used="9.54 MiB",
        quota_value="10 MiB",
        quota_property="refquota",
    ),
    mail=None,
)


def row(name, user_properties, **properties):
    return {
        "name": name,
        "pool": FAUX_POOL,
        "type": "FILESYSTEM",
        "properties": {k: {"value": v} for k, v in properties.items()},
        "user_properties": user_properties,
    }


def pool_row():
    return row(FAUX_POOL, {}, used=1048576, available=9880731648, quota=0, refquota=0)


@pytest.mark.parametrize(
    "rows,alerts",
    [
        (
            [pool_row(), row(FAUX_DS, DEFAULT_THRESHOLDS, quota=10485760, refquota=0, available=10395648)],
            [],
        ),
        (
            [pool_row(), row(FAUX_DS, DEFAULT_THRESHOLDS, usedbydataset=10000000, refquota=10485760, quota=0)],
            [REFQUOTA_CRITICAL],
        ),
        (
            [pool_row(), row(FAUX_DS, {}, usedbydataset=10000000, refquota=10485760, quota=0)],
            [REFQUOTA_CRITICAL],
        ),
    ],
    ids=["quota below threshold", "refquota over critical", "unset thresholds use defaults"],
)
def test_quota_alert_source(monkeypatch, rows, alerts):
    monkeypatch.setattr(quota, "iter_mountinfo", lambda: iter(()))
    middleware = Mock()
    middleware.call_sync2.return_value = rows

    qas = QuotaAlertSource(middleware)
    qas._get_owner = Mock(return_value=0)

    assert qas.check_sync() == alerts
