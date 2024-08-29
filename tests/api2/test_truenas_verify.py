from middlewared.test.integration.utils import ssh


def test_truenas_verify():
    response = ssh('truenas_verify', check=False, complete_response=True)

    # Jenkins vms alter the system files for setup, so truenas_verify should generate errors.
    assert not response['result']
    assert ssh('head /var/log/truenas_verify.log'), 'Test environment should log file verification errors.'
