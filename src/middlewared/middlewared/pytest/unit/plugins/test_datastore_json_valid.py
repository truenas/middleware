import pytest
import sqlalchemy as sa
from sqlalchemy import and_, select
from sqlalchemy.dialects import sqlite
from sqlalchemy.exc import OperationalError

from middlewared.plugins.datastore.filter import FilterMixin


class _Filters(FilterMixin):
    pass


METADATA = sa.MetaData()
TABLE = sa.Table(
    "audit_smb_0_1",
    METADATA,
    sa.Column("ROW_ID", sa.Integer(), primary_key=True),
    sa.Column("event_data", sa.String()),
)

ROWS = [
    {"ROW_ID": 1, "event_data": '{"serviceDescription": "SMB", "passwordType": "NTLMv1"}'},
    {"ROW_ID": 2, "event_data": '{"serviceDescription": "SMB2", "passwordType": "NTLMv2"}'},
    {"ROW_ID": 3, "event_data": '{"serviceDescription": broken'},  # malformed JSON
    {"ROW_ID": 4, "event_data": None},  # NULL column
    {"ROW_ID": 5, "event_data": "123"},  # valid JSON, not an object
    {"ROW_ID": 6, "event_data": ""},  # empty string
]


def _seeded_engine():
    engine = sa.create_engine("sqlite://")
    METADATA.create_all(engine)
    with engine.begin() as conn:
        conn.execute(TABLE.insert(), ROWS)
    return engine


def _run(engine, filters, guard):
    where = _Filters()._filters_to_queryset(filters, TABLE, None, {}, guard_malformed_json=guard)
    qs = select(TABLE.c.ROW_ID).where(and_(*where)).order_by(TABLE.c.ROW_ID)
    with engine.connect() as conn:
        return [row[0] for row in conn.execute(qs).fetchall()]


def test_guard_skips_malformed_row_and_returns_valid_match():
    engine = _seeded_engine()
    result = _run(engine, [["$.event_data.serviceDescription", "=", "SMB"]], guard=True)
    assert result == [1]


def test_unguarded_query_raises_on_malformed_row():
    # Datastore behaviour must be unchanged: without opting in, a malformed row still
    # aborts the statement. This documents that the guard is strictly opt-in.
    engine = _seeded_engine()
    with pytest.raises(OperationalError, match="malformed JSON"):
        _run(engine, [["$.event_data.serviceDescription", "=", "SMB"]], guard=False)


def test_guard_handles_or_nested_json_filters():
    engine = _seeded_engine()
    result = _run(
        engine,
        [
            [
                "OR",
                [
                    ["$.event_data.passwordType", "=", "NTLMv1"],
                    ["$.event_data.passwordType", "=", "NTLMv2"],
                ],
            ]
        ],
        guard=True,
    )
    assert result == [1, 2]


@pytest.mark.parametrize("value", ["SMB", "NTLMv1"])
def test_guard_never_raises_across_edge_values(value):
    # valid-but-non-object (123), NULL, empty string, and malformed rows must all be
    # tolerated by the guard rather than aborting the query.
    engine = _seeded_engine()
    result = _run(engine, [["$.event_data.serviceDescription", "=", value]], guard=True)
    assert all(row_id in {1, 2} for row_id in result)


def test_guarded_sql_wraps_extract_in_json_valid_case():
    where = _Filters()._filters_to_queryset(
        [["$.event_data.serviceDescription", "=", "SMB"]], TABLE, None, {}, guard_malformed_json=True
    )
    compiled = str(and_(*where).compile(dialect=sqlite.dialect()))
    assert "json_valid" in compiled
    assert "CASE WHEN" in compiled


def test_unguarded_sql_is_plain_json_extract():
    where = _Filters()._filters_to_queryset([["$.event_data.serviceDescription", "=", "SMB"]], TABLE, None, {})
    compiled = str(and_(*where).compile(dialect=sqlite.dialect()))
    assert "json_valid" not in compiled
    assert "json_extract" in compiled
