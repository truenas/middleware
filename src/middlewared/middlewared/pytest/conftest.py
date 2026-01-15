from middlewared.fake_env import setup_fake_middleware_env


def pytest_configure():
    setup_fake_middleware_env()
