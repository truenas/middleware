import gc
import os
import pytest

from base64 import b64encode
from contextlib import closing
from middlewared.plugins.system_dataset.utils import SYSDATASET_PATH
from middlewared.utils.tdb import (
    close_sysdataset_tdb_handles,
    get_tdb_handle,
    TDBBatchAction,
    TDBBatchOperation,
    TDBDataType,
    TDBHandle,
    TDBOptions,
    TDBPathType,
)
from middlewared.service_exception import MatchNotFound


@pytest.fixture(scope='module')
def tdbdirs():
    os.makedirs(TDBPathType.PERSISTENT.value, exist_ok=True)
    os.makedirs(TDBPathType.VOLATILE.value, exist_ok=True)
    os.makedirs(SYSDATASET_PATH, exist_ok=True)
    yield


def basic_tdb_ops(hdl: TDBHandle, datatype: TDBDataType):
    match datatype:
        case TDBDataType.JSON:
            data = {'foo': 'bar'}
        case TDBDataType.BYTES:
            data = b64encode(b'foobar_bytes').decode()
        case TDBDataType.STRING:
            data = 'foobar'
        case _:
            raise ValueError(f'{datatype}: unknown data type')

    hdl.store('test_key', data)
    val = hdl.get('test_key')
    assert val == data

    entries = list(hdl.entries())
    assert entries == [{'key': 'test_key', 'value': data}]

    hdl.delete('test_key')
    with pytest.raises(MatchNotFound):
        hdl.get('test_key')

    assert len(list(hdl.entries())) == 0


def batched_tdb_ops(hdl: TDBHandle, datatype: TDBDataType):
    match datatype:
        case TDBDataType.JSON:
            data1 = {'foo1': 'bar1'}
            data2 = {'foo2': 'bar2'}
            data3 = {'foo3': 'bar3'}
        case TDBDataType.BYTES:
            data1 = b64encode(b'foobar_bytes1').decode()
            data2 = b64encode(b'foobar_bytes2').decode()
            data3 = b64encode(b'foobar_bytes3').decode()
        case TDBDataType.STRING:
            data1 = 'foobar1'
            data2 = 'foobar2'
            data3 = 'foobar3'
        case _:
            raise ValueError(f'{datatype}: unknown data type')

    # first try setting three under a lock
    batched_ops = [
        TDBBatchOperation(TDBBatchAction.SET, key='test_key1', value=data1),
        TDBBatchOperation(TDBBatchAction.SET, key='test_key2', value=data2),
        TDBBatchOperation(TDBBatchAction.SET, key='test_key3', value=data3),
    ]
    hdl.batch_op(batched_ops)

    # check that we get same three back
    for key, value in [
        ('test_key1', data1),
        ('test_key2', data2),
        ('test_key3', data3)
    ]:
        assert hdl.get(key) == value

    # now fetch one and delete the other two
    batched_ops = [
        TDBBatchOperation(TDBBatchAction.GET, key='test_key1', value=data1),
        TDBBatchOperation(TDBBatchAction.DEL, key='test_key2'),
        TDBBatchOperation(TDBBatchAction.DEL, key='test_key3'),
    ]
    out = hdl.batch_op(batched_ops)
    assert out['test_key1'] == data1
    assert len(list(hdl.entries())) == 1

    hdl.clear()
    assert len(list(hdl.entries())) == 0


@pytest.mark.parametrize('datatype', TDBDataType)
def test__persistent_tdb(tdbdirs, datatype):
    tdb_name = 'TEST_PERSISTENT'
    expected_path = os.path.join(TDBPathType.PERSISTENT.value, f'{tdb_name}.tdb')
    tdb_options = TDBOptions(TDBPathType.PERSISTENT, datatype)

    with closing(TDBHandle(tdb_name, tdb_options)) as handle:
        basic_tdb_ops(handle, datatype)
        batched_tdb_ops(handle, datatype)
        assert handle.full_path == expected_path

    os.remove(expected_path)


@pytest.mark.parametrize('datatype', TDBDataType)
def test__volatile_tdb(tdbdirs, datatype):
    tdb_name = 'TEST_VOLATILE'
    expected_path = os.path.join(TDBPathType.VOLATILE.value, f'{tdb_name}.tdb')
    tdb_options = TDBOptions(TDBPathType.VOLATILE, datatype)

    with closing(TDBHandle('TEST_VOLATILE', tdb_options)) as handle:
        basic_tdb_ops(handle, datatype)
        batched_tdb_ops(handle, datatype)
        assert handle.full_path == expected_path

    os.remove(expected_path)


@pytest.mark.parametrize('datatype', TDBDataType)
def test__custom_tdb(tmpdir, datatype):
    """ test that creating a custom TDB file works as expected """
    custom_file = os.path.join(tmpdir, 'custom.tdb')
    tdb_options = TDBOptions(TDBPathType.CUSTOM, datatype)

    with closing(TDBHandle(custom_file, tdb_options)) as handle:
        assert handle.full_path == custom_file
        basic_tdb_ops(handle, datatype)
        batched_tdb_ops(handle, datatype)

    os.remove(custom_file)


def test__tdb_connection_caching():
    """ check that TDB handle caching works as expected """
    custom_file = os.path.join(SYSDATASET_PATH, 'sysds.tdb')
    tdb_options = TDBOptions(TDBPathType.CUSTOM, TDBDataType.JSON)
    hdl_id = None

    with get_tdb_handle(custom_file, tdb_options) as hdl:
        hdl_id = id(hdl)
        basic_tdb_ops(hdl, TDBDataType.JSON)

    with get_tdb_handle(custom_file, tdb_options) as hdl:
        assert id(hdl) == hdl_id
        hdl.close()

    with get_tdb_handle(custom_file, tdb_options) as hdl:
        assert id(hdl) != hdl_id
        hdl.close()

    os.remove(custom_file)

    with get_tdb_handle(custom_file, tdb_options) as hdl:
        pass

    close_sysdataset_tdb_handles()


def test__tdb_handle_invalidated_by_delete():
    """ check that file being deleted is properly detected and does not leak """
    custom_file = os.path.join(SYSDATASET_PATH, 'sysds_del.tdb')
    tdb_options = TDBOptions(TDBPathType.CUSTOM, TDBDataType.JSON)
    with get_tdb_handle(custom_file, tdb_options) as hdl:
        os.remove(custom_file)
        assert not hdl.validate_handle()

    close_sysdataset_tdb_handles()


def test__tdb_handle_invalidated_by_rename():
    tdb_options = TDBOptions(TDBPathType.PERSISTENT, TDBDataType.JSON)
    test_payload = {'foo': 'bar'}

    with get_tdb_handle('HANDLE1', tdb_options) as hdl:
        # Intentionally avoid closing this handle because we're
        # testing auto-close of stale handles
        hdl_1_path = hdl.full_path
        hdl_1_id = id(hdl)
        hdl.store('test_key', test_payload)

    with get_tdb_handle('HANDLE2', tdb_options) as hdl:
        hdl_2_id = id(hdl)
        os.rename(hdl_1_path, hdl.full_path)
        assert not hdl.validate_handle()

    with get_tdb_handle('HANDLE1', tdb_options) as hdl:
        # verify we have new TDB file / handle
        assert id(hdl) != hdl_1_id
        # intentionally close so that our final count is correct
        hdl.close()

    with get_tdb_handle('HANDLE2', tdb_options) as hdl:
        # verify we have new TDB file / handle
        assert id(hdl) != hdl_2_id

        # verify we have correct key
        assert hdl.get('test_key') == test_payload

        # intentionally close so that our final count is correct
        hdl.close()
