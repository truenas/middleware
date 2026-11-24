from middlewared.test.integration.utils.server_setup import setup_server


def pytest_sessionstart(session):
    setup_server()
