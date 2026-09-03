import pytest

from middlewared.test.integration.utils import call

LICENSE_UPLOAD_METHOD = "truenas.license.upload"


def test_uploaded_license_is_redacted_in_the_audit_log():
    """
    Whatever installed the license on this system -- CI, TrueNAS Connect or an operator -- went
    through the audited API, so the entry it left behind must carry the redaction placeholder
    instead of the license.
    """
    entries = call(
        "audit.query",
        {
            "query-filters": [["event_data.method", "=", LICENSE_UPLOAD_METHOD]],
            "query-options": {"limit": 1000},
        },
    )
    if not entries:
        pytest.skip(f"nothing has called {LICENSE_UPLOAD_METHOD} on this system")

    for entry in entries:
        params = entry["event_data"]["params"]
        if not params:
            continue

        # Asserting the shape of the placeholder rather than its exact text keeps this independent
        # of how long it is, and holds for a legacy base64 blob as much as for a v2 PEM: any
        # license that reached the audit log unredacted carries something other than an asterisk.
        recorded = str(params[0])
        assert set(recorded) == {"*"}, params
