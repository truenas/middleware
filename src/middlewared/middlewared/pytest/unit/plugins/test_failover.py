import errno
from unittest.mock import MagicMock, Mock, patch

import middlewared
from middlewared.service import CallError
from middlewared.pytest.unit.middleware import Middleware

import importlib.util
spec = importlib.util.spec_from_file_location(
    "middlewared.plugins.failover", "/usr/lib/python3/dist-packages/middlewared/plugins.failover.py"
)
failover = importlib.util.module_from_spec(spec)
spec.loader.exec_module(failover)
middlewared.plugins.failover = failover


def test__journal_write__empty__no_write():
    with patch("middlewared.plugins.failover.os.path.exists", Mock(return_value=False)):
        journal = failover.Journal()
        journal._write = Mock()

    journal.write()

    journal._write.assert_not_called()


def test__journal_write__append_clear__no_write():
    with patch("middlewared.plugins.failover.os.path.exists", Mock(return_value=False)):
        journal = failover.Journal()
        journal._write = Mock()

    journal.append(Mock())
    journal.clear()
    journal.write()

    journal._write.assert_not_called()


def test__journal_write__append_shift__no_write():
    with patch("middlewared.plugins.failover.os.path.exists", Mock(return_value=False)):
        journal = failover.Journal()
        journal._write = Mock()

    journal.append(Mock())
    journal.shift()
    journal.write()

    journal._write.assert_not_called()


def test__journal_write__append_append_shift__write():
    with patch("middlewared.plugins.failover.os.path.exists", Mock(return_value=False)):
        journal = failover.Journal()
        journal._write = Mock()

    journal.append(Mock())
    journal.append(Mock())
    journal.shift()
    journal.write()

    journal._write.assert_called_once()


def test__journal_write__append_shift_append__write():
    with patch("middlewared.plugins.failover.os.path.exists", Mock(return_value=False)):
        journal = failover.Journal()
        journal._write = Mock()

    journal.append(Mock())
    journal.shift()
    journal.append(Mock())
    journal.write()

    journal._write.assert_called_once()


def test__journal_sync__flush_journal():
    middleware = Middleware()
    middleware['failover.status'] = Mock(return_value='MASTER')
    middleware['failover.call_remote'] = Mock()
    middleware['alert.oneshot_delete'] = Mock()
    journal = MagicMock()
    journal.__bool__.side_effect = [True, False]
    journal.peek.return_value = [Mock(), Mock()]
    journal_sync = failover.JournalSync(middleware, Mock(), journal)

    assert journal_sync._flush_journal()

    middleware['failover.call_remote'].assert_called_once_with('datastore.sql', journal.peek.return_value)
    assert not journal_sync.last_query_failed
    middleware['alert.oneshot_delete'].assert_called_once_with('FailoverSyncFailed', None)
    journal.shift.assert_called_once()


def test__journal_sync__flush_journal__error():
    middleware = Middleware()
    middleware['failover.status'] = Mock(return_value='MASTER')
    middleware['failover.call_remote'] = Mock(side_effect=CallError('Invalid SQL query'))
    middleware['alert.oneshot_create'] = Mock()
    journal = MagicMock()
    journal.__bool__.side_effect = [True, False]
    journal.peek.return_value = [Mock(), Mock()]
    journal_sync = failover.JournalSync(middleware, Mock(), journal)

    assert not journal_sync._flush_journal()

    assert journal_sync.last_query_failed
    middleware['alert.oneshot_create'].assert_called_once_with('FailoverSyncFailed', None)
    journal.shift.assert_not_called()


def test__journal_sync__flush_journal__network_error():
    middleware = Middleware()
    middleware['failover.status'] = Mock(return_value='MASTER')
    middleware['failover.call_remote'] = Mock(side_effect=CallError('Connection refused', errno.ECONNREFUSED))
    journal = MagicMock()
    journal.__bool__.side_effect = [True, False]
    journal.peek.return_value = [Mock(), Mock()]
    journal_sync = failover.JournalSync(middleware, Mock(), journal)

    assert not journal_sync._flush_journal()

    assert not journal_sync.last_query_failed
    journal.shift.assert_not_called()
