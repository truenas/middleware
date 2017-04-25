import pytest
import configparser

from client import Client

from middlewared.client import Client as WSClient


class ConfigTarget(object):

    def __init__(self):
        self.config = configparser.ConfigParser()
        self.file_path = 'target.conf'
        self.config_section = 'Target'
        self.config.read(self.file_path)

    def target_hostname(self):
        return self.config.get(self.config_section, 'hostname')

    def target_api(self):
        return self.config.get(self.config_section, 'api')

    def target_username(self):
        return self.config.get(self.config_section, 'username')

    def target_password(self):
        return self.config.get(self.config_section, 'password')


class Connection(object):

    def __init__(self):
        conf = ConfigTarget()
        self.rest = Client(
            f'http://{conf.target_hostname()}',
            conf.target_api(),
            conf.target_username(),
            conf.target_password(),
        )
        self.ws = WSClient(f'ws://{conf.target_hostname()}/websocket')
        self.ws.call('auth.login', conf.target_username(), conf.target_password())

connection = Connection()

@pytest.fixture
def conn():
    global connection
    return connection
