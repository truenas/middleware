def test_smb_config(conn):
    service = conn.rest.get('smb')

    assert service.status_code == 200
    assert isinstance(service.json(), dict) is True
