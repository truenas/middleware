def test_mail_config(conn):
    service = conn.rest.get('mail')

    assert service.status_code == 200
    assert isinstance(service.json(), dict) is True
