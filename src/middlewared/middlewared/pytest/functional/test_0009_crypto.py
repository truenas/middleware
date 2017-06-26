def test_crypto_cert_query(conn):
    req = conn.rest.get('certificate')
    assert req.status_code == 200, req.text
    assert isinstance(req.json(), list)


def test_crypto_ca_query(conn):
    req = conn.rest.get('certificateauthority')
    assert req.status_code == 200, req.text
    assert isinstance(req.json(), list)
