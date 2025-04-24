import base64
from threading import Lock

import googleapiclient
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import google_auth_httplib2
import httplib2

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

                # `google-api-python-client` is not thread-safe which can lead to interpreter segfaults.
                # We fix this by providing every thread its own `httplib2.Http()` object.
                # See https://googleapis.github.io/google-api-python-client/docs/thread_safety.html
                self._service = build(
                    "gmail", "v1",
                    credentials=credentials,
                    requestBuilder=lambda http, *args, **kwargs: googleapiclient.http.HttpRequest(
                        google_auth_httplib2.AuthorizedHttp(credentials, http=httplib2.Http()),
                        *args, **kwargs,
                    ),
                )

            return self._service

    def close(self):
        with self._lock:
            if self._service is not None:
                self._service.close()
                self._service = None


class MailService(Service):
    gmail_service = None

    @private
    def gmail_initialize(self):
        config = self.middleware.call_sync("mail.config")
        if self.gmail_service is not None:
            self.gmail_service.close()
        self.gmail_service = self.middleware.call_sync("mail.gmail_build_service", config)

    @private
    def gmail_build_service(self, config):
        if config["oauth"] and config["oauth"]["provider"] == "gmail":
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
            if gmail_service == self.gmail_service:
                credentials = gmail_service._service._http.credentials
                self._set_gmail_config({
                    "provider": "gmail",
                    "client_id": credentials.client_id,
                    "client_secret": credentials.client_secret,
                    "refresh_token": credentials.refresh_token,
                })
        except BrokenPipeError:
            if not _retry_broken_pipe:
                raise

            self.middleware.logger.debug("BrokenPipeError in gmail_send, retrying")
            if self.gmail_service is not None:
                self.gmail_service.close()
            return self.gmail_send(message, config, _retry_broken_pipe=False)

        if gmail_service != self.gmail_service:
            gmail_service.close()

    @private
    def _set_gmail_config(self, config):
        existing_config = self.middleware.call_sync("datastore.config", "system.email")
        if existing_config["em_oauth"] != config:
            self.middleware.call_sync("datastore.update", "system.email", existing_config["id"], {"em_oauth": config})


async def setup(middleware):
    await middleware.call("mail.gmail_initialize")
