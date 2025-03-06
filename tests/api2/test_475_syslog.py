from time import sleep

import pytest
from auto_config import password, user
from middlewared.test.integration.utils import call, ssh
from middlewared.test.integration.utils.client import truenas_server


def do_syslog(ident, message, facility='syslog.LOG_USER', priority='syslog.LOG_INFO'):
    """
    This generates a syslog message on the TrueNAS server we're currently testing.
    We don't need to override IP addr or creds because we are not a syslog target.
    """
    cmd = 'python3 -c "import syslog;'
    cmd += f'syslog.openlog(ident=\\\"{ident}\\\", facility={facility});'
    cmd += f'syslog.syslog({priority},\\\"{message}\\\");syslog.closelog()"'
    ssh(cmd)


def check_syslog(log_path, message, target_ip=None, target_user=user, target_passwd=password, timeout=30):
    """
    Common function to check whether a particular message exists in a log file.
    This will be used to check local and remote syslog servers.

    Current implementation performs simple grep through the log file, and so
    onus is on test developer to not under-specify `message` in order to avoid
    false positives.
    """
    target_ip = target_ip or truenas_server.ip
    sleep_time = 1
    while timeout > 0:
        found = ssh(
            f'grep -R "{message}" {log_path}',
            check=False,
            user=target_user,
            password=target_passwd,
            ip=target_ip
        )
        if not found:
            sleep(sleep_time)
            timeout -= sleep_time
        else:
            return found


@pytest.mark.parametrize('params', [
    {
        'ident': 'iscsi-scstd',
        'msg': 'ZZZZ: random scst test',
        'path': '/var/log/scst.log',
    },
    {
        'ident': 'iscsi-scstd',
        'msg': 'ZZZZ: random scst test',
        'path': '/var/log/scst.log',  # This is just to make sure our exclude filter works as intended
    },
])
def test_local_syslog_filter(request, params):
    """
    This test validates that our syslog-ng filters are correctly placing
    messages into their respective paths in /var/log
    """
    do_syslog(
        params['ident'],
        params['msg'],
        params.get('facility', 'syslog.LOG_USER'),
        params.get('priority', 'syslog.LOG_INFO')
    )
    assert check_syslog(params['path'], params['msg'], timeout=10)


@pytest.mark.parametrize('log_path', [
    '/var/log/messages',
    '/var/log/syslog',
    '/var/log/daemon.log'
])
def test_filter_leak(request, log_path):
    """
    This test validates that our exclude filter works properly and that
    particularly spammy applications aren't polluting useful logs.
    """
    results = ssh(f'grep -R "ZZZZ:" {log_path}', complete_response=True, check=False)
    assert results['result'] is False, str(results['result'])


def test_set_remote_syslog(request):
    """
    Basic test to validate that setting a remote syslog target
    doesn't break syslog-ng config
    """
    try:
        data = call('system.advanced.update', {'syslogserver': '127.0.0.1'})
        assert data['syslogserver'] == '127.0.0.1'
        call('service.restart', 'syslogd', {'silent': False})
    finally:
        call('system.advanced.update', {'syslogserver': ''})


def test_set_remote_syslog_with_TLS_transport():
    """
    Confirm expected settings in syslog-ng.conf when selecting TLS transport.
    NOTE: This test does NOT confirm end-to-end functionality.
    TODO: Add remote syslog server to enable end-to-end testing
    """
    restore_cmd = {"syslogserver": "", "syslog_transport": "UDP", "syslog_tls_certificate": None}
    remote = "127.0.0.1"
    port = "5140"
    transport = "TLS"
    tls_cmd = {"syslogserver": f"{remote}:{port}", "syslog_transport": f"{transport}"}
    try:
        data = call('system.advanced.update', tls_cmd)
        assert data['syslog_transport'] == 'TLS'
        conf = ssh('grep "destination loghost" /etc/syslog-ng/syslog-ng.conf', complete_response=True, check=False)
        assert f"port({port})" in conf['stdout'], f"conf={conf}"
        assert 'transport("tls")' in conf['stdout'], f"conf={conf}"
        assert 'tls(ca-file("/etc/ssl/certs/ca-certificates.crt"))' in conf['stdout'], f"conf={conf}"

    finally:
        call('system.advanced.update', restore_cmd)
