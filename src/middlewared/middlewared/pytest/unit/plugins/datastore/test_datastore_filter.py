"""
Test for FilterMixin._filters_to_queryset JSON filter handling
"""
from dataclasses import dataclass
import json

import pytest
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Engine, select

from middlewared.plugins.datastore.filter import FilterMixin


@dataclass(frozen=True)
class TestFilterMixin(FilterMixin):
    engine: Engine
    table: Table


@pytest.fixture(scope='module')
def filter_mixin():
    engine = create_engine('sqlite:///:memory:', echo=False)
    metadata = MetaData()

    audit_table = Table(
        'audit_MIDDLEWARE_0_1',
        metadata,
        Column('ROW_ID', Integer, primary_key=True),
        Column('event_data', String),
        Column('username', String),
    )
    metadata.create_all(engine)

    # Insert test data
    with engine.connect() as conn:
        conn.execute(audit_table.insert(), [
            {
                'ROW_ID': 1,
                'username': 'admin',
                'event_data': json.dumps({
                    'method': 'user.delete',
                    'params': [38],
                    'nested': {'key': 'value1'}
                })
            },
            {
                'ROW_ID': 2,
                'username': 'admin',
                'event_data': json.dumps({
                    'method': 'user.create',
                    'params': [39],
                    'nested': {'key': 'value2'}
                })
            },
            {
                'ROW_ID': 3,
                'username': 'root',
                'event_data': json.dumps({
                    'method': 'user.delete',
                    'params': [40, 41],
                    'nested': {'key': 'value3'}
                })
            },
        ])
        conn.commit()

    return TestFilterMixin(engine, audit_table)


def execute_filters(mixin_obj: TestFilterMixin, filters):
    where_clauses = mixin_obj._filters_to_queryset(
        filters,
        mixin_obj.table,
        None,
        {}
    )
    stmt = select(mixin_obj.table).where(*where_clauses)

    with mixin_obj.engine.connect() as conn:
        return conn.execute(stmt).fetchall()


@pytest.mark.parametrize('filters, expected_ids', [
    (
        [['$.event_data.params', '=', [38]]],
        {1}
    ),
    (
        [['$.event_data.nested', '=', {'key': 'value1'}]],
        {1}
    ),
    (
        [['$.event_data.params', '=', [40, 41]]],
        {3}
    ),
    (
        [['username', '=', 'admin']],
        {1, 2}
    ),
    (
        [['username', '=', 'admin'], ['$.event_data.params', '=', [38]]],
        {1}
    ),
    (
        [['$.event_data.method', '=', 'user.delete']],
        {1, 3}
    ),
])
def test_filters_to_queryset(filter_mixin, filters, expected_ids):
    rows = execute_filters(filter_mixin, filters)
    assert {row.ROW_ID for row in rows} == expected_ids
