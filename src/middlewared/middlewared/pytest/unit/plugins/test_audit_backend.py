import sqlite3

import pytest
from sqlalchemy.dialects import sqlite

from middlewared.alert.source.audit import AuditDatabaseCorruptedAlertClass
from middlewared.plugins.audit.backend import AuditBackendService, SQLConn, decode_audit_json
from middlewared.plugins.audit.table import AUDIT_TABLES
from middlewared.plugins.datastore.schema import SchemaMixin
from middlewared.pytest.unit.middleware import Middleware

# AuditDatabaseCorrupted key handling -------------------------------------


@pytest.mark.asyncio
async def test_corruption_alert_cleared_by_service_key():
    # The alert is keyed on the service alone, so oneshot_delete passes the scalar service
    # name. This pins the create/clear key contract in unit CI.
    klass = AuditDatabaseCorruptedAlertClass(Middleware())
    alert = await klass.create({"service": "MIDDLEWARE", "count": 1})
    assert await klass.delete([alert], "MIDDLEWARE") == []


@pytest.mark.asyncio
async def test_corruption_alert_other_service_not_cleared():
    # Clearing one service must not drop another service's alert.
    klass = AuditDatabaseCorruptedAlertClass(Middleware())
    alert = await klass.create({"service": "MIDDLEWARE", "count": 1})
    assert await klass.delete([alert], "SMB") == [alert]


# decode_audit_json --------------------------------------------------------


def test_decode_audit_json_valid_object():
    assert decode_audit_json('{"a": 1}') == {"a": 1}


def test_decode_audit_json_malformed_text_falls_back_to_raw():
    assert decode_audit_json("{not valid json") == "{not valid json"


def test_decode_audit_json_bad_ejson_payload_falls_back_to_raw():
    # Syntactically valid JSON, but ejson cannot reconstruct the $date payload and raises
    # EJSONDecodeError (a ValueError, not a JSONDecodeError). It must fall back to the raw
    # string rather than propagating and failing the whole audit query.
    raw = '{"$date": "not-a-number"}'
    assert decode_audit_json(raw) == raw


# SELECT-side json_extract guard ------------------------------------------


class _Cols(SchemaMixin):
    pass


# __get_audit_column only depends on self._get_col, so we can drive it with a bare SchemaMixin.
_get_audit_column = AuditBackendService.__dict__["_AuditBackendService__get_audit_column"]


def test_select_json_path_is_guarded_with_json_valid():
    column = _get_audit_column(_Cols(), AUDIT_TABLES["MIDDLEWARE"], "$.service_data.origin", "origin")
    compiled = str(column.compile(dialect=sqlite.dialect()))
    assert "json_valid" in compiled
    assert "CASE WHEN" in compiled


def test_select_plain_column_is_not_wrapped():
    column = _get_audit_column(_Cols(), AUDIT_TABLES["MIDDLEWARE"], "username", "username")
    compiled = str(column.compile(dialect=sqlite.dialect()))
    assert "json_valid" not in compiled


# SQLConn.count_malformed --------------------------------------------------


def _seed_audit_db(path):
    con = sqlite3.connect(path)
    con.executescript(
        "CREATE TABLE audit_MIDDLEWARE_0_1 ("
        "audit_id TEXT, message_timestamp INTEGER, timestamp TEXT, address TEXT, "
        "username TEXT, session TEXT, service TEXT, service_data TEXT, event TEXT, "
        "event_data TEXT, success BOOLEAN);"
    )
    con.executemany(
        "INSERT INTO audit_MIDDLEWARE_0_1 (event_data, service_data) VALUES (?, ?)",
        [
            ('{"a": 1}', '{"b": 2}'),  # both valid
            ("{malformed", '{"b": 2}'),  # malformed event_data
            ('{"a": 1}', "{malformed"),  # malformed service_data
            (None, None),  # NULLs are ignored
            ('{"a": 1}', None),  # valid + NULL
        ],
    )
    con.commit()
    con.close()


@pytest.fixture
def audit_conn(tmp_path):
    db_path = tmp_path / "MIDDLEWARE.db"
    _seed_audit_db(str(db_path))
    conn = SQLConn("MIDDLEWARE", 0.1)
    conn.path = str(db_path)
    conn.setup()
    yield conn


def test_count_malformed_counts_only_unparseable_rows(audit_conn):
    assert audit_conn.count_malformed() == 2


def test_count_malformed_never_raises_on_corrupted_table(audit_conn):
    # Adding a row malformed in both JSON columns is still counted once and does not raise.
    con = sqlite3.connect(audit_conn.path)
    con.execute("INSERT INTO audit_MIDDLEWARE_0_1 (event_data, service_data) VALUES ('{x', '{y')")
    con.commit()
    con.close()
    assert audit_conn.count_malformed() == 3
