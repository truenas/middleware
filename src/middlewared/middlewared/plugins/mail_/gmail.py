import base64
from threading import Lock

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from middlewared.service import private, Service


class GmailService:
    def __init__(self, config):
        self.config = config

        self._lock = Lock()
        self._service = None

    def __eq__(self, other):
        return isinstance(other, GmailService) and self.config["oauth"] == other.config["oauth"]

    @property
    def service(self):
        with self._lock:
            if self._service is None:
                credentials = Credentials.from_authorized_user_info(self.config["oauth"])
                self._service = build("gmail", "v1", credentials=credentials)

            return self._service

    def close(self):
        with self._lock:
            if self._service is not None:
                self._service.close()
                self._service = None


class MailService(Service):
    gmail_service = None

    @private
    async def gmail_initialize(self):
        config = await self.middleware.call("mail.config")
        if self.gmail_service is not None:
            self.gmail_service.close()
        self.gmail_service = await self.middleware.call("mail.gmail_build_service", config)

    @private
    async def gmail_build_service(self, config):
        if config["oauth"]:
            return GmailService(config)

        return None

    @private
    def gmail_send(self, message, config, _retry_broken_pipe=True):
        gmail_service = self.middleware.call_sync("mail.gmail_build_service", config)
        if gmail_service == self.gmail_service:
            # Use existing gmail service if credentials match to avoid extra access token refresh
            gmail_service = self.gmail_service
        else:
            _retry_broken_pipe = False

        if gmail_service is None:
            raise RuntimeError("GMail service is not initialized")

        try:
            gmail_service.service.users().messages().send(userId="me", body={
                "raw": base64.urlsafe_b64encode(message.as_string().encode("ascii")).decode("ascii"),
            }).execute()
        except BrokenPipeError:
            if not _retry_broken_pipe:
                raise

            self.middleware.logger.debug("BrokenPipeError in gmail_send, retrying")
            if self.gmail_service is not None:
                self.gmail_service.close()
            return self.gmail_send(message, config, _retry_broken_pipe=False)

        if gmail_service != self.gmail_service:
            gmail_service.close()


async def setup(middleware):
    await middleware.call("mail.gmail_initialize")
