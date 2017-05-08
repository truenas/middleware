def test_cifs_config(conn):
    service = conn.rest.get('cifs')

    assert service.status_code == 200
    assert isinstance(service.json(), dict) is True
