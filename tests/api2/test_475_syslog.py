from middlewared.test.integration.utils import call


def test_07_check_can_set_remote_syslog(request):
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
