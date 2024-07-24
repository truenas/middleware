import logging
import uuid

from middlewared.auth import SessionManagerCredentials
from middlewared.utils.origin import Origin

logger = logging.getLogger(__name__)


class App:
    def __init__(self, origin: Origin):
        self.origin = origin
        self.session_id = str(uuid.uuid4())
        self.authenticated = False
        self.authenticated_credentials: SessionManagerCredentials | None = None
        self.py_exceptions = False
        self.websocket = False
        self.rest = False
