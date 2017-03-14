import pytest
import configparser

from client import Client


class ConfigTarget(object):

    def __init__(self):
        self.config = configparser.ConfigParser()
        self.file_path = 'target.conf'
        self.config_section = 'Target'
        self.config.read(self.file_path)

    def target_uri(self):
        return self.config.get(self.config_section, 'uri')

    def target_api(self):
        return self.config.get(self.config_section, 'api')

    def target_username(self):
        return self.config.get(self.config_section, 'username')

    def target_password(self):
        return self.config.get(self.config_section, 'password')


class Authentication(object):

    def __init__(self):
        conf = ConfigTarget()
        self.connect = Client(conf.target_uri(), conf.target_api(),
                              conf.target_username(), conf.target_password())


@pytest.fixture
def auth_prepare():
    return Authentication()
