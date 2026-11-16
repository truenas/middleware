import pytest

from middlewared.test.integration.utils import call, ha_test

LICENSE_UPLOAD_METHOD = "truenas.license.upload"


@ha_test
def test_uploaded_license_is_redacted_in_the_audit_log():
    entries = call(
        "audit.query",
        {
            "query-filters": [["event_data.method", "=", LICENSE_UPLOAD_METHOD]],
            "query-options": {"limit": 1000},
        },
    )
    assert entries

    for entry in entries:
        params = entry["event_data"]["params"]
        if not params:
            continue

        # Asserting the shape of the placeholder rather than its exact text keeps this independent
        # of how long it is, and holds for a legacy base64 blob as much as for a v2 PEM: any
        # license that reached the audit log unredacted carries something other than an asterisk.
        recorded = str(params[0])
        assert set(recorded) == {"*"}, params
