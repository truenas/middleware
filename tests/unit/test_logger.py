import json
import logging
import logging.handlers
import os
import pytest
import subprocess

from collections import deque
from contextlib import contextmanager
from middlewared.logger import (
    ALL_LOG_FILES,
    DEFAULT_IDENT,
    DEFAULT_LOGFORMAT,
    DEFAULT_SYSLOG_PATH,
    LOGFILE,
    QFORMATTER,
    setup_syslog_handler,
    TNSyslogHandler,
)
from time import sleep

SYSLOG_WRITE_WAIT = 1


def remove_logfile(path):
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


@pytest.fixture(scope='function')
def current_test_name(request):
    return request.node.name


@pytest.fixture(scope='function')
def test_message(current_test_name):
    return f'This is a test message for test {current_test_name}'


@pytest.fixture(scope='function')
def fallback_handler(tmpdir):
    logfile = os.path.join(tmpdir, 'fallback.log')
    fallback_handler = logging.handlers.RotatingFileHandler(logfile, 'a', 10485760, 5, 'utf-8')
    fallback_handler.setLevel(logging.DEBUG)
    fallback_handler.setFormatter(logging.Formatter(DEFAULT_LOGFORMAT, "%Y/%m/%d %H:%M:%S"))

    try:
        yield (logfile, fallback_handler)
    finally:
        remove_logfile(logfile)


@contextmanager
def disable_syslog():
    subprocess.run(['service', 'syslog-ng', 'stop'])

    try:
        yield
    finally:
        subprocess.run(['service', 'syslog-ng', 'start'])
        # Give a little extra buffer for syslog-ng to fully start
        sleep(SYSLOG_WRITE_WAIT)


@pytest.fixture(scope='function')
def broken_syslog(current_test_name):
    handler = TNSyslogHandler(address='/var/empty/canary', pending_queue=deque())
    logger = logging.getLogger(current_test_name)
    logger.addHandler(handler)

    try:
        yield (logger, handler)
    finally:
        handler.close()


@pytest.fixture(scope='function')
def broken_syslog_with_fallback(broken_syslog, fallback_handler):
    logger, syslog_handler = broken_syslog
    logfile, fallback = fallback_handler

    syslog_handler.set_fallback_handler(fallback)

    yield (logger, syslog_handler, logfile)


@pytest.fixture(scope='function')
def working_syslog(current_test_name):
    """ Set up syslog logger to use middleware rules (via ident) so that it
    can successfully write to the middleware log file. """

    handler = TNSyslogHandler(address=DEFAULT_SYSLOG_PATH, pending_queue=deque())
    handler.setFormatter(QFORMATTER)
    handler.ident = DEFAULT_IDENT
    logger = logging.getLogger(current_test_name)
    logger.addHandler(handler)

    try:
        yield (logger, handler)
    finally:
        handler.close()


def test__pending_queue(broken_syslog, test_message):
    """ Verify that when syslog connection is broken messages are queued """
    logger, handler = broken_syslog
    assert handler.pending_queue is not None
    assert handler.fallback_handler is None

    logger.critical(test_message)
    assert len(handler.pending_queue) == 1
    assert handler.pending_queue[0].msg == test_message


def test__fallback_handler(broken_syslog_with_fallback, test_message):
    """ Verify that fallback handler results in writes to log file """
    logger, handler, logfile = broken_syslog_with_fallback

    assert handler.pending_queue is not None
    assert handler.fallback_handler is not None

    logger.critical(test_message)
    assert len(handler.pending_queue) == 1
    assert handler.pending_queue[0].msg == test_message

    with open(logfile, 'r') as f:
        contents = f.read()
        assert test_message in contents


def test__working_syslog_handler(working_syslog, test_message):
    """ Verify that syslog handler writes to the middleware log """
    logger, handler = working_syslog
    assert handler.pending_queue is not None
    assert handler.fallback_handler is None

    logger.critical(test_message)
    assert len(handler.pending_queue) == 0
    sleep(SYSLOG_WRITE_WAIT)

    with open(LOGFILE, 'r') as f:
        contents = f.read()
        assert test_message in contents


def test__syslog_handler_recovery(working_syslog, test_message, current_test_name):
    """ Verify that pending queue is properly drained and written to syslog target """
    logger, handler = working_syslog
    assert handler.pending_queue is not None
    assert handler.fallback_handler is None

    with disable_syslog():
        logger.critical(test_message)
        assert len(handler.pending_queue) == 1

    # Queue only gets drained on message emit
    flush_message = f'Flush message for {current_test_name}'
    logger.critical(flush_message)

    # Queue should be fully drained now that syslog is working
    assert len(handler.pending_queue) == 0
    sleep(SYSLOG_WRITE_WAIT)

    # Message should now be written to file in order in which
    # it was initially emitted
    with open(LOGFILE, 'r') as f:
        contents = f.read()
        assert f'{test_message}\n{flush_message}' in contents


@pytest.mark.parametrize('tnlog', ALL_LOG_FILES)
def test__middleware_logger_paths(tnlog, test_message):
    """ Verify that syslog filtering rules work properly for backends """
    logger = setup_syslog_handler(tnlog, None)
    logger.critical(test_message)

    sleep(SYSLOG_WRITE_WAIT)
    with open(tnlog.logfile, 'r') as f:
        contents = f.read()
        assert test_message in contents


def test__syslog_exception_parameterization(working_syslog, test_message):
    logger, handler = working_syslog
    assert handler.pending_queue is not None
    assert handler.fallback_handler is None

    log_line = None

    try:
        os.stat('/var/empty/nonexistent')
    except Exception:
        logger.critical(test_message, exc_info=True)

    sleep(SYSLOG_WRITE_WAIT)
    with open(LOGFILE, 'r') as f:
        for line in f:
            if line.startswith(test_message):
                log_line = line
                break

    assert log_line is not None
    assert '@cee' in log_line

    exc = log_line.split('@cee:')[1]
    data = json.loads(exc)
    assert data['TNLOG']['type'] == 'PYTHON_EXCEPTION'
    assert 'time' in data['TNLOG']
    assert 'FileNotFoundError' in data['TNLOG']['exception']
