import base64
import dataclasses
import logging
import smtplib
import time

from middlewared.api.current import MailEntry
from middlewared.service import CallError
from middlewared.utils.microsoft import get_microsoft_access_token

logger = logging.getLogger(__name__)


@dataclasses.dataclass(slots=True)
class OutlookToken:
    token: str
    expires_at: float


class Outlook:
    outlook_tokens: dict[str, OutlookToken] = {}

    def xoauth2(self, server: smtplib.SMTP, config: MailEntry) -> None:
        server.ehlo()

        oauth = config.oauth.get_secret_value()
        if not oauth:
            raise CallError("OAuth is not configured")

        if token := self._get_outlook_token(config.fromemail, oauth.refresh_token):
            code, response = self._do_xoauth2(server, config.fromemail, token)
            if 200 <= code <= 299:
                return

            logger.warning("Outlook XOAUTH2 failed: %r %r. Refreshing access token", code, response)

        logger.debug("Requesting Outlook access token")
        oauth_response = get_microsoft_access_token(
            oauth.client_id,
            oauth.client_secret,
            oauth.refresh_token,
            "https://outlook.office.com/SMTP.Send openid offline_access",
        )

        new_token: str = oauth_response["access_token"]
        self._set_outlook_token(config.fromemail, oauth.refresh_token, new_token, oauth_response["expires_in"])

        code, response = self._do_xoauth2(server, config.fromemail, new_token)
        if 200 <= code <= 299:
            return

        raise CallError("Outlook XOAUTH2 failed: %r %r" % (code, response))

    def _get_outlook_token(self, email: str, refresh_token: str) -> str | None:
        for key, expired_token in list(self.outlook_tokens.items()):
            if expired_token.expires_at < time.monotonic() - 5:
                self.outlook_tokens.pop(key)

        if token := self.outlook_tokens.get(email + refresh_token):
            return token.token

        return None

    def _set_outlook_token(self, email: str, refresh_token: str, token: str, expires_in: int) -> None:
        self.outlook_tokens[email + refresh_token] = OutlookToken(token, time.monotonic() + expires_in)

    def _do_xoauth2(self, server: smtplib.SMTP, email: str, access_token: str) -> tuple[int, bytes]:
        auth_string = f"user={email}\1auth=Bearer {access_token}\1\1"
        return server.docmd("AUTH XOAUTH2", base64.b64encode(auth_string.encode()).decode())


outlook = Outlook()
