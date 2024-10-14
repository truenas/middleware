import pam
import re
import threading

from dataclasses import dataclass
from datetime import datetime, UTC
from middlewared.utils.allowlist import Allowlist
from middlewared.utils.auth import AuthMech, AuthenticatorAssuranceLevel
from time import monotonic


class SessionManagerCredentials:
    is_user_session = False
    allowlist = None

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
        return False

    def has_role(self, role):
        return False

    def notify_used(self):
        pass

    def logout(self):
        pass

    def dump(self):
        return {}


class UserSessionManagerCredentials(SessionManagerCredentials):
    """ Credentials for authenticated user session """

    def __init__(self, user: dict, assurance: AuthenticatorAssuranceLevel | None):
        """
        user: dictionary generated by `auth.authenticate_user`

        assurance: authenticator assurance level for the session. This
        may be None if the session is authenticated by virtue of unix domain
        socket connection.

        Our default is AAL1 which allows authenticated sessions to use
        credentials for up to 30 days before requiring reauthentication, and
        does not set an inactivity timeout.

        See comments in utils/auth.py for more information.
        """
        now = monotonic()
        self.user = user
        self.assurance = assurance
        self.allowlist = Allowlist(user["privilege"]["allowlist"])
        self.is_user_session = True
        self.login_at = datetime.now(UTC)
        self.expiry = None
        self.inactivity_timeout = None
        self.last_used_at = now

        if assurance:
            self.expiry = now + self.assurance.max_session_age
            self.inactivity_timeout = self.assurance.max_inactivity

    def notify_used(self):
        if self.inactivity_timeout:
            now = monotonic()
            if now < self.last_used_at + self.inactivity_timeout:
                self.last_used_at = now

    def is_valid(self):
        if self.assurance and (now := monotonic()) > self.expiry:
            return False

        if self.inactivity_timeout:
            if now > self.last_used_at + self.inactivity_timeout:
                return False

        return True

    def authorize(self, method, resource):
        if not self.is_valid():
            return False

        return self.allowlist.authorize(method, resource)

    def has_role(self, role):
        return role in self.user["privilege"]["roles"]

    def dump(self):
        return {
            "username": self.user["username"],
            "login_at": self.login_at
        }


class ApiKeySessionManagerCredentials(UserSessionManagerCredentials):
    """ Credentials for a specific user account on TrueNAS
    Authenticated by user-linked API key
    """

    def __init__(self, user: dict, api_key: dict, assurance: AuthenticatorAssuranceLevel):
        super().__init__(user, assurance)
        self.api_key = api_key

    def dump(self):
        out = super().dump()
        return out | {
            "api_key": {
                "id": self.api_key["id"],
                "name": self.api_key["name"],
            }
        }


class UnixSocketSessionManagerCredentials(UserSessionManagerCredentials):
    """ Credentials for a specific user account on TrueNAS
    Authenticated by unix domain socket connection
    """
    def __init__(self, user: dict):
        super().__init__(user, None)


class LoginPasswordSessionManagerCredentials(UserSessionManagerCredentials):
    """ Credentials for a specific user account on TrueNAS
    Authenticated by username + password combination.
    """
    pass


class LoginTwofactorSessionManagerCredentials(LoginPasswordSessionManagerCredentials):
    """ Credentials for a specific user account on TrueNAS
    Authenticated by username + password combination and additional
    OTP token.
    """
    pass


class TokenSessionManagerCredentials(SessionManagerCredentials):
    def __init__(self, token_manager, token):
        self.root_credentials = token.root_credentials()

        self.token_manager = token_manager
        self.token = token
        self.is_user_session = self.root_credentials.is_user_session
        if self.is_user_session:
            self.user = self.root_credentials.user

        self.allowlist = self.root_credentials.allowlist

    def is_valid(self):
        if not self.root_credentials.is_valid():
            return False

        return self.token.is_valid()

    def authorize(self, method, resource):
        return self.token.parent_credentials.authorize(method, resource)

    def has_role(self, role):
        return self.token.parent_credentials.has_role(role)

    def notify_used(self):
        self.root_credentials.notify_used()
        self.token.notify_used()

    def logout(self):
        self.token_manager.destroy(self.token)

    def dump(self):
        data = {
            "parent": dump_credentials(self.token.parent_credentials),
        }
        if self.is_user_session:
            data["username"] = self.user["username"]

        return data


class TrueNasNodeSessionManagerCredentials(SessionManagerCredentials):
    def authorize(self, method, resource):
        return True


@dataclass()
class AuthenticationContext:
    """
    This stores PAM context for authentication mechanisms that implement
    challenge-response protocol. We need to keep reference for PAM handle
    to handle any required PAM conversations.
    """
    pam_lock: threading.Lock = threading.Lock()
    pam_hdl: pam.PamAuthenticator = pam.pam()
    next_mech: AuthMech | None = None
    auth_data: dict | None = None


class FakeApplication:
    authenticated_credentials = SessionManagerCredentials()


def fake_app():
    return FakeApplication()


def dump_credentials(credentials):
    return {
        "credentials": credentials.class_name(),
        "credentials_data": credentials.dump(),
    }
