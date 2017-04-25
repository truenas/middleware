def test_get_services(conn):
    services = conn.rest.get('core/get_services')

    assert services.status_code == 200
    assert isinstance(services.json(), dict) is True


def test_get_methods(conn):
    methods = conn.rest.post('core/get_methods')

    assert methods.status_code == 200
    assert isinstance(methods.json(), dict) is True


def test_get_jobs(conn):
    jobs = conn.rest.get('core/get_jobs')

    assert jobs.status_code == 200
    assert isinstance(jobs.json(), list) is True


def test_ping(conn):
    ping = conn.rest.get('core/ping')

    assert ping.status_code == 200
    assert ping.json() == 'pong'
