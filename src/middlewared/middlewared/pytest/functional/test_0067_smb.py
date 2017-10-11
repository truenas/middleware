def test_smb_config(conn):
    req = conn.rest.get('smb')

    assert req.status_code == 200, req.text
    assert isinstance(req.json(), dict) is True
