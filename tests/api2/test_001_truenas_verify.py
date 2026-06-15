import pytest
import time

from middlewared.test.integration.utils import call, ssh


VERIFY_LOG_PREAMBLE = '/var/log/audit/truenas_verify'
DEFAULT_VERIFY_LOG_NAME = f"{VERIFY_LOG_PREAMBLE}.log"
CUSTOM_NAME = "init_test"
CUSTOM_VERIFY_LOG_NAME = f"{VERIFY_LOG_PREAMBLE}.{CUSTOM_NAME}.log"


def delete_file(fname):
    ssh(f'rm -f {fname}')


def file_exists(fname):
    return ssh(f'test -f {fname}', check=False, complete_response=True)['result']


@pytest.fixture(scope='module')
def verify_setup():
    # Setup:  Remove existing default log file
    delete_file(DEFAULT_VERIFY_LOG_NAME)

    try:
        yield
    finally:
        # Clean up
        for file in [DEFAULT_VERIFY_LOG_NAME, CUSTOM_VERIFY_LOG_NAME]:
            delete_file(file)


def test_truenas_verify_install_log():
    """
    The audit subsystem generates an 'as-installed' log at first boot. This
    should be clean with no detections or errors: the running system must match
    the shipped mtree.

    This test deliberately lives in api2 and is ordered to run immediately
    after ssh setup, before any later test mutates system configuration, so we
    validate the genuine first-boot baseline. It previously lived in tests/unit,
    but that suite runs locally on the NAS and must mutate the base install in
    order to operate, which polluted the baseline (e.g. the functioning-dpkg
    sysext being transiently merged).
    """
    current_version = call('system.version')
    log = ssh(f"cat /var/log/audit/truenas_verify.{current_version}.log")
    # The last entry is an empty string
    tnv_init = log.splitlines()[:-1]

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
    # truenas_verify exits non-zero when discrepancies are detected, so we
    # don't want ssh() to assert on the return code here.
    verify_cmd = ' '.join(['truenas_verify'] + params)

    match type:
        case 'default':
            ssh(verify_cmd, check=False)
            assert file_exists(DEFAULT_VERIFY_LOG_NAME), f"Expected to find {DEFAULT_VERIFY_LOG_NAME}"
        case 'init':
            ssh(verify_cmd, check=False)
            assert file_exists(CUSTOM_VERIFY_LOG_NAME), f"Expected to find {CUSTOM_VERIFY_LOG_NAME}"
        case 'syslog':
            ssh(verify_cmd, check=False)
            time.sleep(1)   # Wait a sec for the output to get logged
            log_entry = ssh("grep 'discrepancies found' /var/log/syslog | tail -n 1")
            assert 'discrepancies found' in log_entry, f"Expected to find verify message:\n{log_entry}"
