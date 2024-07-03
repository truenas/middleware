from middlewared.test.integration.utils import call, ssh

def test_system_advanced_login_banner():
    results = call('system.advanced.update', {
        'login_banner': 'TrueNAS login banner.'
    })
    results = call('system.advanced.config')
    assert results['login_banner'] == 'TrueNAS login banner.'
    results = ssh('grep Banner /etc/ssh/sshd_config', complete_response=True)
    assert results['result']
