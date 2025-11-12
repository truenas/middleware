"""
Test for FilterMixin._filters_to_queryset JSON filter handling
"""
from dataclasses import dataclass
import json

import pytest
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Engine, select

from middlewared.plugins.datastore.filter import FilterMixin


class TestFilterMixin(FilterMixin):
    """Concrete implementation for testing"""
    
    def __init__(self, engine, table):
        self.engine = engine
        self.table = table
    
    def _get_col(self, table, name, prefix):
        """Get column from table - required by FilterMixin"""
        return getattr(table.c, name)


@dataclass
class DBAssets:
    filter_mixin: TestFilterMixin
    audit_table: Table
    engine: Engine


@pytest.fixture(scope='module')
def db_assets():
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

    filter_mixin = TestFilterMixin(engine, audit_table)

    return DBAssets(filter_mixin, audit_table, engine)


def test_list_value_json_field(db_assets):
    filters = [['$.event_data.params', '=', [38]]]
    where_clauses = db_assets.filter_mixin._filters_to_queryset(
        filters,
        db_assets.audit_table,
        None,
        {}
    )
    stmt = select(db_assets.audit_table).where(*where_clauses)
    
    with db_assets.engine.connect() as conn:
        result = conn.execute(stmt)
        rows = result.fetchall()
        
        if rows:
            for row in rows:
                data = json.loads(row.event_data)
        
        assert len(rows) == 1, f"Expected 1 row, got {len(rows)}"
        assert rows[0].ROW_ID == 1, f"Expected ROW_ID=1, got {rows[0].ROW_ID}"


def test_dict_value_nested_json_field(db_assets):
    filters = [['$.event_data.nested', '=', {'key': 'value1'}]]
    where_clauses = db_assets.filter_mixin._filters_to_queryset(
        filters,
        db_assets.audit_table,
        None,
        {}
    )
    stmt = select(db_assets.audit_table).where(*where_clauses)

    with db_assets.engine.connect() as conn:
        result = conn.execute(stmt)
        rows = result.fetchall()

        assert len(rows) == 1, f"Expected 1 row, got {len(rows)}"
        assert rows[0].ROW_ID == 1, f"Expected ROW_ID=1, got {rows[0].ROW_ID}"


def test_multi_element_list(db_assets):
    filters = [['$.event_data.params', '=', [40, 41]]]
    where_clauses = db_assets.filter_mixin._filters_to_queryset(
        filters,
        db_assets.audit_table,
        None,
        {}
    )
    stmt = select(db_assets.audit_table).where(*where_clauses)
    
    with db_assets.engine.connect() as conn:
        result = conn.execute(stmt)
        rows = result.fetchall()

        assert len(rows) == 1, f"Expected 1 row, got {len(rows)}"
        assert rows[0].ROW_ID == 3, f"Expected ROW_ID=3, got {rows[0].ROW_ID}"


def test_non_json(db_assets):
    filters = [['username', '=', 'admin']]
    where_clauses = db_assets.filter_mixin._filters_to_queryset(
        filters,
        db_assets.audit_table,
        None,
        {}
    )
    stmt = select(db_assets.audit_table).where(*where_clauses)

    with db_assets.engine.connect() as conn:
        result = conn.execute(stmt)
        rows = result.fetchall()

        assert len(rows) == 2, f"Expected 2 rows, got {len(rows)}"


def test_json_and_non_json(db_assets):
    filters = [
        ['username', '=', 'admin'],
        ['$.event_data.params', '=', [38]]
    ]
    where_clauses = db_assets.filter_mixin._filters_to_queryset(
        filters,
        db_assets.audit_table,
        None,
        {}
    )
    stmt = select(db_assets.audit_table).where(*where_clauses)

    with db_assets.engine.connect() as conn:
        result = conn.execute(stmt)
        rows = result.fetchall()

        assert len(rows) == 1, f"Expected 1 row, got {len(rows)}"
        assert rows[0].ROW_ID == 1, f"Expected ROW_ID=1, got {rows[0].ROW_ID}"
        assert rows[0].username == 'admin', f"Expected username='admin'"


def test_string_value_json_field(db_assets):
    filters = [['$.event_data.method', '=', 'user.delete']]
    where_clauses = db_assets.filter_mixin._filters_to_queryset(
        filters,
        db_assets.audit_table,
        None,
        {}
    )
    stmt = select(db_assets.audit_table).where(*where_clauses)

    with db_assets.engine.connect() as conn:
        result = conn.execute(stmt)
        rows = result.fetchall()

        assert len(rows) == 2, f"Expected 2 rows, got {len(rows)}"
