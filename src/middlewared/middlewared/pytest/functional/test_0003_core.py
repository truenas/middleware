def test_get_services(auth_prepare):
    services = auth_prepare.connect.get('core/get_services')

    assert services.status_code == 200
    assert isinstance(services.json(), dict) is True


def test_get_methods(auth_prepare):
    methods = auth_prepare.connect.post('core/get_methods')

    assert methods.status_code == 200
    assert isinstance(methods.json(), dict) is True


def test_get_jobs(auth_prepare):
    jobs = auth_prepare.connect.get('core/get_jobs')

    assert jobs.status_code == 200
    assert isinstance(jobs.json(), list) is True


def test_ping(auth_prepare):
    ping = auth_prepare.connect.get('core/ping')

    assert ping.status_code == 200
    assert ping.json() == 'pong'
