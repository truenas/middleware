"""Round trip the USB port identity migration against a real (in memory) database."""
import base64
import importlib.util
import json
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, event, text

from middlewared.api.v26_0_0.container_device import ContainerDeviceEntry
from middlewared.api.v26_0_0.vm_device import VMDeviceEntry
from middlewared.utils import pwenc


MIGRATION_PATH = (
    Path(__file__).parents[3] / 'alembic' / 'versions' / '26.0' / '2026-08-04_10-00_usb_device_port_identity.py'
)

# Each row is (id, stored attributes, attributes expected afterwards, or None if the row must go).
VM_ROWS = [
    (
        1,
        {'dtype': 'USB', 'device': 'usb_1_4', 'usb': None, 'controller_type': 'nec-xhci'},
        {'dtype': 'USB', 'port': '1-4', 'usb': None, 'controller_type': 'nec-xhci'},
    ),
    (
        2,
        {'dtype': 'USB', 'device': 'usb_5_1_1', 'usb': None, 'controller_type': 'qemu-xhci'},
        {'dtype': 'USB', 'port': '5-1.1', 'usb': None, 'controller_type': 'qemu-xhci'},
    ),
    (
        3,
        {'dtype': 'USB', 'device': None, 'usb': {'vendor_id': '0xABC', 'product_id': '2'},
         'controller_type': 'nec-xhci'},
        {'dtype': 'USB', 'port': None, 'usb': {'vendor_id': '0x0abc', 'product_id': '0x0002'},
         'controller_type': 'nec-xhci'},
    ),
    (
        4,
        {'dtype': 'USB', 'port': '1-4.2', 'usb': None, 'controller_type': 'nec-xhci'},
        {'dtype': 'USB', 'port': '1-4.2', 'usb': None, 'controller_type': 'nec-xhci'},
    ),
    (5, {'dtype': 'USB', 'device': 'usb_usb1', 'usb': None, 'controller_type': 'nec-xhci'}, None),
    (6, {'dtype': 'USB', 'device': None, 'usb': None, 'controller_type': 'nec-xhci'}, None),
    (
        7,
        {'dtype': 'USB', 'device': None, 'usb': {'vendor_id': '0x12345', 'product_id': '0x0002'},
         'controller_type': 'nec-xhci'},
        None,
    ),
    (8, {'dtype': 'USB', 'device': 'pci_0000_00_02_0', 'usb': None, 'controller_type': 'nec-xhci'}, None),
    (
        9,
        {'dtype': 'DISK', 'path': '/dev/zvol/tank/vm', 'type': 'AHCI'},
        {'dtype': 'DISK', 'path': '/dev/zvol/tank/vm', 'type': 'AHCI'},
    ),
]

CONTAINER_ROWS = [
    # Written by 26.0 code, so `usb_1_5` is a bus and device number rather than a port.
    (1, {'dtype': 'USB', 'device': 'usb_1_5', 'usb': None}, None),
    (2, {'dtype': 'USB', 'device': '1-4.2', 'usb': None}, None),
    (3, {'dtype': 'USB', 'device': 'usb_usb1', 'usb': None}, None),
    (4, {'dtype': 'USB', 'device': None, 'usb': None}, None),
    (
        5,
        {'dtype': 'USB', 'device': None, 'usb': {'vendor_id': '0xABC', 'product_id': '2'}},
        {'dtype': 'USB', 'port': None, 'usb': {'vendor_id': '0x0abc', 'product_id': '0x0002'}},
    ),
    (
        6,
        {'dtype': 'USB', 'port': '1-4.2', 'usb': None},
        {'dtype': 'USB', 'port': '1-4.2', 'usb': None},
    ),
    (
        7,
        {'dtype': 'NIC', 'nic_attach': 'br0'},
        {'dtype': 'NIC', 'nic_attach': 'br0'},
    ),
]


@pytest.fixture(autouse=True)
def stub_pwenc(monkeypatch):
    """Swap the pwenc primitives for something that needs no secret on disk."""
    monkeypatch.setattr(pwenc, 'pwenc_encrypt', base64.b64encode)
    monkeypatch.setattr(pwenc, 'pwenc_decrypt', base64.b64decode)


@pytest.fixture
def migration():
    spec = importlib.util.spec_from_file_location('usb_device_port_identity', MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def conn():
    engine = create_engine('sqlite://')
    with engine.connect() as conn:
        conn.execute(text(
            'CREATE TABLE vm_device (id INTEGER PRIMARY KEY, attributes TEXT NOT NULL, vm_id INTEGER, '
            '"order" INTEGER)'
        ))
        conn.execute(text(
            'CREATE TABLE container_device (id INTEGER PRIMARY KEY, attributes TEXT NOT NULL, '
            'container_id INTEGER, "order" INTEGER)'
        ))
        for table, rows, owner_column in (
            ('vm_device', VM_ROWS, 'vm_id'), ('container_device', CONTAINER_ROWS, 'container_id'),
        ):
            for id_, attributes, _ in rows:
                conn.execute(
                    text(f'INSERT INTO {table} (id, attributes, {owner_column}, "order") '
                         'VALUES (:id, :attributes, 1, 1)'),
                    {'id': id_, 'attributes': pwenc.encrypt(json.dumps(attributes))},
                )

        yield conn


def _run_upgrade(conn, migration):
    """Run the migration and hand back every write statement it issued."""
    statements = []

    def record(conn, cursor, statement, parameters, context, executemany):
        if statement.strip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')):
            statements.append(statement)

    event.listen(conn, 'before_cursor_execute', record)
    try:
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
    finally:
        event.remove(conn, 'before_cursor_execute', record)

    return statements


def _read_back(conn, table):
    return {
        row['id']: json.loads(pwenc.decrypt(row['attributes']))
        for row in conn.execute(text(f'SELECT * FROM {table}')).mappings().all()
    }


@pytest.mark.parametrize('table,rows', [('vm_device', VM_ROWS), ('container_device', CONTAINER_ROWS)])
def test_upgrade_rewrites_and_drops_the_right_rows(conn, migration, table, rows):
    _run_upgrade(conn, migration)

    stored = _read_back(conn, table)

    assert stored == {id_: expected for id_, _, expected in rows if expected is not None}


@pytest.mark.parametrize('table,model,extra', [
    ('vm_device', VMDeviceEntry, {'vm': 1, 'order': 1}),
    ('container_device', ContainerDeviceEntry, {'container': 1}),
])
def test_upgrade_leaves_only_rows_the_api_can_read(conn, migration, table, model, extra):
    _run_upgrade(conn, migration)

    for id_, attributes in _read_back(conn, table).items():
        model(id=id_, attributes=attributes, **extra)


def test_upgrade_is_a_no_op_the_second_time(conn, migration):
    _run_upgrade(conn, migration)
    before = {table: _read_back(conn, table) for table in ('vm_device', 'container_device')}

    assert _run_upgrade(conn, migration) == []
    assert {table: _read_back(conn, table) for table in ('vm_device', 'container_device')} == before


def test_upgrade_warns_about_every_row_it_drops(conn, migration, caplog):
    dropped = [
        (table, id_)
        for table, rows in (('vm_device', VM_ROWS), ('container_device', CONTAINER_ROWS))
        for id_, _, expected in rows
        if expected is None
    ]

    with caplog.at_level('WARNING', logger=migration.logger.name):
        _run_upgrade(conn, migration)

    assert len(caplog.records) == len(dropped)
    for (table, id_), record in zip(dropped, caplog.records):
        message = record.getMessage()
        assert f'Removing {table} row {id_!r}' in message
        assert 'has to be added again' in message
