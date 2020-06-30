import pytest


@pytest.mark.parametrize('group', ['ldap', 'nss', 'network', 'pam'])
def test_etc_generate(conn, group):
    conn.ws.call('etc.generate', group)


def test_etc_generate_checkpoint(conn):
    for checkpoint in conn.ws.call('etc.get_checkpoints'):
        conn.ws.call('etc.generate_checkpoint', checkpoint)
