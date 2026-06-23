import shlex

import pytest

from middlewared.test.integration.utils import call, ssh

AUDIT_DB = "/audit/MIDDLEWARE.db"
TABLE = "audit_MIDDLEWARE_0_1"
TAG = "nas140907-test"
ALERT_KLASS = "AuditDatabaseCorrupted"


def _run_sql(sql):
    full = f"PRAGMA busy_timeout=5000; {sql}"
    return ssh(f"sqlite3 {AUDIT_DB} {shlex.quote(full)}")


def _insert_corrupt_rows():
    now = int(ssh("date +%s").strip())
    # Row A: non-JSON text -> json_valid() is false.
    # Row B: valid JSON whose $date payload ejson cannot reconstruct -> EJSONDecodeError on decode.
    _run_sql(
        f"INSERT INTO {TABLE} (audit_id, message_timestamp, service, event, event_data) "
        f"VALUES ('{TAG}-a', {now}, 'MIDDLEWARE', 'METHOD_CALL', '{{malformed json');"
        f"INSERT INTO {TABLE} (audit_id, message_timestamp, service, event, event_data) "
        f"VALUES ('{TAG}-b', {now}, 'MIDDLEWARE', 'METHOD_CALL', '{{\"$date\": \"not-a-number\"}}');"
    )


def _delete_corrupt_rows():
    _run_sql(f"DELETE FROM {TABLE} WHERE audit_id LIKE '{TAG}%';")


def _scan():
    ssh("midclt call auditbackend.scan_corruption")


def _corruption_alerts():
    return [
        a
        for a in call("alert.list")
        if a["klass"] == ALERT_KLASS and a["args"].get("service") == "MIDDLEWARE"
    ]


@pytest.fixture(scope="module")
def corrupt_audit_db():
    _insert_corrupt_rows()
    try:
        yield
    finally:
        _delete_corrupt_rows()
        _scan()


def test_json_path_filter_does_not_abort_on_malformed_row(corrupt_audit_db):
    # A JSONPath WHERE filter evaluates json_extract over every scanned row, including the
    # corrupt ones. Without the guard this raises sqlite3.OperationalError: malformed JSON.
    result = call(
        "audit.query",
        {
            "services": ["MIDDLEWARE"],
            "query-filters": [["event_data.method", "=", "user.create"]],
            "query-options": {"limit": 10},
        },
    )
    assert isinstance(result, list)


def test_select_as_json_path_projects_null_for_corrupt_rows(corrupt_audit_db):
    # SELECT AS on a JSON path evaluates json_extract in the projection; the guard must
    # yield NULL for unparseable rows instead of aborting the query.
    result = call(
        "audit.query",
        {
            "services": ["MIDDLEWARE"],
            "query-filters": [["audit_id", "^", TAG]],
            "query-options": {
                "select": ["audit_id", ["event_data.method", "method"]],
                "limit": 10,
            },
        },
    )
    by_id = {row["audit_id"]: row for row in result}
    assert set(by_id) == {f"{TAG}-a", f"{TAG}-b"}
    assert by_id[f"{TAG}-a"]["method"] is None
    assert by_id[f"{TAG}-b"]["method"] is None


def test_scan_raises_corruption_alert(corrupt_audit_db):
    _scan()
    assert _corruption_alerts(), "expected AuditDatabaseCorrupted alert for MIDDLEWARE"


def test_scan_clears_alert_once_rows_removed(corrupt_audit_db):
    _delete_corrupt_rows()
    _scan()
    assert not _corruption_alerts(), (
        "alert should be cleared after corrupt rows are removed"
    )
