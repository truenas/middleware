import re

import pytest
from pytest_dependency import depends

from auto_config import pool_name, user, password
from functions import SSH_TEST
from middlewared.test.integration.utils import call


G = 1024 * 1024 * 1024


@pytest.mark.parametrize("datasets,expected_alerts", [
    (
        {
            "": {
                "used": 900,
                "quota": 1 * G,
            }
        },
        [
            {"formatted": r"Quota exceeded on dataset tank/quota_test. Used 8|9[0-9.]+% \(8|9[0-9.]+ MiB of 1 GiB\)."},
        ]
    ),
    (
        {
            "": {
                "used": 118,
                "quota": 10 * G,
                "refquota": 1 * G,
            }
        },
        [
            # There was a false positive:
            # {"formatted": r"Quota exceeded on dataset tank/quota_test. Used 91.[0-9]+% \(9.[0-9]+ GiB of 10 GiB\)."},
        ]
    ),
    (
        {
            "": {
                "used": 100,
                "quota": 1000000000 * G,
            }
        },
        [
            # There should be no quota alerts if quota is set to a larger value than dataset size
        ]
    ),
])
def test_dataset_quota_alert(request, datasets, expected_alerts):
    assert "" in datasets

    try:
        for dataset, params in datasets.items():
            used = params.pop("used", None)

            call("pool.dataset.create", {"name": f"{pool_name}/quota_test/{dataset}".rstrip("/"), **params})

            if used is not None:
                results = SSH_TEST(f'dd if=/dev/urandom of=/mnt/{pool_name}/quota_test/{dataset}/blob '
                                   f'bs=1M count={used}', user, password)
                assert results['result'] is True, results

        call("alert.initialize")
        call("core.bulk", "alert.process_alerts", [[]], job=True)

        alerts = [alert for alert in call("alert.list") if alert["source"] == "Quota"]
        assert len(alerts) == len(expected_alerts), alerts

        for alert, expected_alert in zip(alerts, expected_alerts):
            for k, v in expected_alert.items():
                if k == "formatted":
                    assert re.match(v, alert[k]), (alert, expected_alert, k)
                else:
                    assert alert[k] == v, (alert, expected_alert, k)
    finally:
        call("pool.dataset.delete", f"{pool_name}/quota_test", {
            "recursive": True,
        })
