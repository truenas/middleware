import re

from middlewared.utils.allowlist import Allowlist


class SessionManagerCredentials:
    @classmethod
    def class_name(cls):
        return re.sub(
            r"([A-Z])",
            r"_\1",
            cls.__name__.replace("SessionManagerCredentials", "")
        ).lstrip("_").upper()

    def login(self):
        pass

    def is_valid(self):
        return True

    def authorize(self, method, resource):
        return True

    def has_role(self, role):
        return True

    def notify_used(self):
        pass

    def logout(self):
        pass

    def dump(self):
        return {}


class UserSessionManagerCredentials(SessionManagerCredentials):
    def __init__(self, user):
        self.user = user
        self.allowlist = Allowlist(user["privilege"]["allowlist"])

    def authorize(self, method, resource):
        return self.allowlist.authorize(method, resource)

    def has_role(self, role):
        return role in self.user["privilege"]["roles"]

    def dump(self):
        return {
            "username": self.user["username"],
        }


class UnixSocketSessionManagerCredentials(UserSessionManagerCredentials):
    pass


class RootTcpSocketSessionManagerCredentials(SessionManagerCredentials):
    pass


class LoginPasswordSessionManagerCredentials(UserSessionManagerCredentials):
    pass


class ApiKeySessionManagerCredentials(SessionManagerCredentials):
    def __init__(self, api_key):
        self.api_key = api_key

    def authorize(self, method, resource):
        return self.api_key.authorize(method, resource)

    def dump(self):
        return {
            "api_key": {
                "id": self.api_key.api_key["id"],
                "name": self.api_key.api_key["name"],
            }
        }


class TrueNasNodeSessionManagerCredentials(SessionManagerCredentials):
    pass


def is_ha_connection(remote_addr, remote_port):
    return remote_port <= 1024 and remote_addr in ('169.254.10.1', '169.254.10.2')


class FakeApplication:
    authenticated_credentials = SessionManagerCredentials()


def fake_app():
    return FakeApplication()
