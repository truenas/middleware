import configparser
import os
import pytest

from middlewared.client import Client as WSClient

try:
    from .client import Client
except ImportError:
    pass
else:
    class ConfigTarget(object):

        def __init__(self):
            self.config = configparser.ConfigParser()
            self.file_path = 'target.conf'
            self.config_section = 'Target'
            self.config.read(self.file_path)

        def target_hostname(self):
            return os.environ.get('TEST_HOSTNAME') or self.config.get(self.config_section, 'hostname')

        def target_api(self):
            return os.environ.get('TEST_API') or self.config.get(self.config_section, 'api')

        def target_username(self):
            return os.environ.get('TEST_USERNAME') or self.config.get(self.config_section, 'username')

        def target_password(self):
            return os.environ.get('TEST_PASSWORD') or self.config.get(self.config_section, 'password')


    class Connection(object):

        def __init__(self):
            self.conf = ConfigTarget()
            self.rest = Client(
                f'http://{self.conf.target_hostname()}',
                self.conf.target_api(),
                self.conf.target_username(),
                self.conf.target_password(),
            )
            self.ws = WSClient(f'ws://{self.conf.target_hostname()}/websocket')
            self.ws.call('auth.login', self.conf.target_username(), self.conf.target_password())

    connection = Connection()

    @pytest.fixture
    def conn():
        global connection
        return connection
