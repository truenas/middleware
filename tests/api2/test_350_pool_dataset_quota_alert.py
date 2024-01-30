#!/usr/bin/env python3

# License: BSD

import sys
import os
import re
import pytest
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import DELETE, GET, POST, SSH_TEST
from auto_config import ip, pool_name, user, password

G = 1024 * 1024 * 1024
pytestmark = pytest.mark.zfs


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

            result = POST(
                "/pool/dataset/", {
                    "name": f"{pool_name}/quota_test/{dataset}".rstrip("/"),
                    **params,
                }
            )
            assert result.status_code == 200, result.text

            if used is not None:
                results = SSH_TEST(f'dd if=/dev/urandom of=/mnt/{pool_name}/quota_test/{dataset}/blob '
                                   f'bs=1M count={used}', user, password, ip)
                assert results['result'] is True, results

        results = SSH_TEST("midclt call alert.initialize", user, password, ip)
        assert results['result'] is True, results

        results = SSH_TEST("midclt call -job core.bulk alert.process_alerts '[[]]'", user, password, ip)
        assert results['result'] is True, results

        result = GET("/alert/list/")
        assert result.status_code == 200, result.text

        alerts = [alert for alert in result.json() if alert["source"] == "Quota"]

        assert len(alerts) == len(expected_alerts), alerts

        for alert, expected_alert in zip(alerts, expected_alerts):
            for k, v in expected_alert.items():
                if k == "formatted":
                    assert re.match(v, alert[k]), (alert, expected_alert, k)
                else:
                    assert alert[k] == v, (alert, expected_alert, k)
    finally:
        result = DELETE(f"/pool/dataset/id/{pool_name}%2Fquota_test/", {
            "recursive": True,
        })
        assert result.status_code == 200, result.text
