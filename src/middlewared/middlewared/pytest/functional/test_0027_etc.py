import pytest


@pytest.mark.parametrize('group', ['ldap', 'nss', 'network', 'pam'])
def test_etc_generate(conn, group):
    conn.ws.call('etc.generate', group)


def test_etc_generate_checkpoint(conn):
    conn.ws.call('etc.generate_checkpoint', 'default')
