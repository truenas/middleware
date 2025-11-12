import logging

from middlewared.auth import SessionManagerCredentials, AuthenticationContext
from middlewared.utils.crypto import ssl_uuid4
from middlewared.utils.origin import ConnectionOrigin

logger = logging.getLogger(__name__)


class App:
    def __init__(self, origin: ConnectionOrigin):
        self.origin = origin
        self.session_id = str(ssl_uuid4())
        self.authenticated = False
        self.authentication_context = AuthenticationContext()
        self.authenticated_credentials: SessionManagerCredentials | None = None
        self.legacy_jobs = True
        self.private_methods = False
        self.py_exceptions = False
        self.websocket = False
