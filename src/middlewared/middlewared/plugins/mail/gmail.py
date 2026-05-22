import base64
from email.mime.base import MIMEBase
from threading import Lock
from typing import Any

from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
import google_auth_httplib2
import googleapiclient
from googleapiclient.discovery import build
import httplib2

from middlewared.alert.base import AlertCategory, AlertClassConfig, AlertLevel, OneShotAlertClass
from middlewared.api.current import MailEntry
from middlewared.service import ServiceContext


class GMailConfigurationDiscardedAlert(OneShotAlertClass):
    config = AlertClassConfig(
        category=AlertCategory.SYSTEM,
        level=AlertLevel.WARNING,
        title="GMail OAuth Configuration Discarded",
        text=(
            "Your Gmail OAuth configuration was discarded due to a token refresh error. "
            'Please go to the system email configuration and click the "Log In to Gmail" button again.'
        ),
        deleted_automatically=False,
        keys=[],
    )


class GmailService:
    def __init__(self, config: MailEntry) -> None:
        self.config = config

        self._lock = Lock()
        self._service = None

    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, GmailService)
            and self.config.oauth.get_secret_value() == other.config.oauth.get_secret_value()
        )

    @property
    def service(self) -> Any:
        with self._lock:
            if self._service is None:
                credentials = Credentials.from_authorized_user_info(
                    self.config.oauth.get_secret_value().model_dump()  # type: ignore[union-attr]
                )  # type: ignore[no-untyped-call]

                # `google-api-python-client` is not thread-safe which can lead to interpreter segfaults.
                # We fix this by providing every thread its own `httplib2.Http()` object.
                # See https://googleapis.github.io/google-api-python-client/docs/thread_safety.html
                self._service = build(
                    "gmail",
                    "v1",
                    credentials=credentials,
                    requestBuilder=lambda http, *args, **kwargs: googleapiclient.http.HttpRequest(
                        google_auth_httplib2.AuthorizedHttp(credentials, http=httplib2.Http()),
                        *args,
                        **kwargs,
                    ),
                )

            return self._service

    def close(self) -> None:
        with self._lock:
            if self._service is not None:
                self._service.close()
                self._service = None


class GMail:
    gmail_service: GmailService | None = None

    def initialize(self, context: ServiceContext) -> None:
        config = context.call_sync2(context.s.mail.config)
        if self.gmail_service is not None:
            self.gmail_service.close()

        self.gmail_service = self.build_service(config)

    def build_service(self, config: MailEntry) -> GmailService | None:
        oauth = config.oauth.get_secret_value()
        if oauth and oauth.provider == "gmail":
            return GmailService(config)

        return None

    def send(
        self,
        context: ServiceContext,
        message: MIMEBase,
        config: MailEntry,
        _retry_broken_pipe: bool = True,
    ) -> None:
        context.middleware.call_sync("network.general.will_perform_activity", "mail")

        gmail_service = self.build_service(config)
        if gmail_service == self.gmail_service:
            # Use existing gmail service if credentials match to avoid extra access token refresh
            gmail_service = self.gmail_service
        else:
            _retry_broken_pipe = False

        if gmail_service is None:
            raise RuntimeError("GMail service is not initialized")

        try:
            gmail_service.service.users().messages().send(
                userId="me",
                body={
                    "raw": base64.urlsafe_b64encode(message.as_string().encode("ascii")).decode("ascii"),
                },
            ).execute()
            if gmail_service == self.gmail_service:
                credentials = gmail_service._service._http.credentials  # type: ignore[attr-defined]
                self._set_gmail_config(
                    context,
                    {
                        "provider": "gmail",
                        "client_id": credentials.client_id,
                        "client_secret": credentials.client_secret,
                        "refresh_token": credentials.refresh_token,
                    },
                )
        except BrokenPipeError:
            if not _retry_broken_pipe:
                raise

            context.middleware.logger.debug("BrokenPipeError in gmail_send, retrying")
            if self.gmail_service is not None:
                self.gmail_service.close()

            return self.send(context, message, config, _retry_broken_pipe=False)
        except RefreshError as e:
            # e.args were ('invalid_grant: Bad Request', {'error': 'invalid_grant', 'error_description': 'Bad Request'})
            # There's no documented structure for this error, so it might change at any time, let's be extra safe
            if "invalid_grant" in str(e):
                if gmail_service == self.gmail_service:
                    # Currently setup credentials were used. Discard them
                    context.middleware.logger.warning(f"GMail credentials RefreshError: {e}. Discarding GMail OAuth")
                    self._set_gmail_config(context, None)
                    self.initialize(context)
                    context.call_sync2(context.s.alert.oneshot_create, GMailConfigurationDiscardedAlert())

            raise

        if gmail_service != self.gmail_service:
            gmail_service.close()

    def _set_gmail_config(self, context: ServiceContext, config: dict[str, Any] | None) -> None:
        existing_config = context.middleware.call_sync("datastore.config", "system.email")
        if existing_config["em_oauth"] != config:
            context.middleware.call_sync(
                "datastore.update", "system.email", existing_config["id"], {"em_oauth": config}
            )


gmail = GMail()
