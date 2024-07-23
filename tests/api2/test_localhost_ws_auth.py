from middlewared.test.integration.utils import ssh


def test__authentication_required_localhost():
    cmd = 'midclt -u ws://localhost/websocket call user.query'
    resp = ssh(cmd, check=False, complete_response=True)

    assert not resp['result']

    assert 'Not authenticated' in resp['stderr']

