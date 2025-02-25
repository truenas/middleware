import os
import pytest
import subprocess
import time

from truenas_api_client import Client


VERIFY_LOG_PREAMBLE = '/var/log/audit/truenas_verify'
DEFAULT_VERIFY_LOG_NAME = f"{VERIFY_LOG_PREAMBLE}.log"
CUSTOM_NAME = "init_test"
CUSTOM_VERIFY_LOG_NAME = f"{VERIFY_LOG_PREAMBLE}.{CUSTOM_NAME}.log"


def delete_file(fname):
    try:
        os.unlink(fname)
    except FileNotFoundError:
        pass


@pytest.fixture(scope='module')
def verify_setup():
    # Setup:  Remove existing default log file
    delete_file(DEFAULT_VERIFY_LOG_NAME)

    try:
        yield os.path.exists(DEFAULT_VERIFY_LOG_NAME)
    finally:
        # Clean up
        for file in [DEFAULT_VERIFY_LOG_NAME, CUSTOM_VERIFY_LOG_NAME]:
            delete_file(file)


def test_truenas_verify_install_log():
    """
    The audit subsystem generates an 'as-installed' log
    This should be clean with no detections or errors
    """
    with Client() as c:
        current_version = c.call('system.version')
        with open(f"/var/log/audit/truenas_verify.{current_version}.log", 'r') as f:
            # The last entry is an empty string
            tnv_init = f.read().splitlines()[:-1]

        # A clean system will have only one entry: The header.
        assert len(tnv_init) == 1, f"Found unexpected entries\n{tnv_init}"


@pytest.mark.parametrize(
    'type,params', [
        ("default", []),
        ("init", ["init", CUSTOM_NAME]),
        ("syslog", ["syslog"])
    ],
    ids=["default", "init", "syslog"]
)
def test_truenas_verify(verify_setup, type, params):
    """
    Exercize and confirm the three call types: default, init, syslog
    """
    verify_cmd = ['truenas_verify'] + params
    if type != 'syslog':
        subprocess.run(verify_cmd)

    match type:
        case 'default':
            assert os.path.exists(DEFAULT_VERIFY_LOG_NAME), f"Expected to find {DEFAULT_VERIFY_LOG_NAME}"
        case 'init':
            assert os.path.exists(CUSTOM_VERIFY_LOG_NAME), f"Expected to find {CUSTOM_VERIFY_LOG_NAME}"
        case 'syslog':
            with open('/var/log/syslog', 'r') as logfile:
                # Go to the end of the file
                logfile.seek(0, 2)
                subprocess.run(verify_cmd)
                time.sleep(1)   # Wait a sec for the output to get logged
                log_entries = logfile.readlines()
            assert 'discrepancies found' in log_entries[0], f"Expected to find verify message:\n{log_entries[0]}"

