import base64
import dataclasses
import smtplib
import time

from middlewared.service import CallError, private, Service
from middlewared.utils.microsoft import get_microsoft_access_token


@dataclasses.dataclass(slots=True)
class OutlookToken:
    token: str
    expires_at: float


class MailService(Service):
    outlook_tokens: dict[str, OutlookToken] = {}

    @private
    def outlook_xoauth2(self, server: smtplib.SMTP, config: dict):
        server.ehlo()

        if token := self._get_outlook_token(config["fromemail"], config["oauth"]["refresh_token"]):
            code, response = self._do_xoauth2(server, config["fromemail"], token)
            if 200 <= code <= 299:
                return

            self.logger.warning("Outlook XOAUTH2 failed: %r %r. Refreshing access token", code, response)

        self.logger.debug("Requesting Outlook access token")
        response = get_microsoft_access_token(
            config["oauth"]["client_id"],
            config["oauth"]["client_secret"],
            config["oauth"]["refresh_token"],
            "https://outlook.office.com/SMTP.Send openid offline_access",
        )

        token = response["access_token"]
        self._set_outlook_token(config["fromemail"], config["oauth"]["refresh_token"], token, response["expires_in"])

        code, response = self._do_xoauth2(server, config["fromemail"], token)
        if 200 <= code <= 299:
            return

        raise CallError("Outlook XOAUTH2 failed: %r %r" % (code, response))

    def _get_outlook_token(self, email: str, refresh_token: str) -> str | None:
        for key, token in list(self.outlook_tokens.items()):
            if token.expires_at < time.monotonic() - 5:
                self.outlook_tokens.pop(key)

        if token := self.outlook_tokens.get(email + refresh_token):
            return token.token

    def _set_outlook_token(self, email: str, refresh_token: str, token: str, expires_in: int):
        self.outlook_tokens[email + refresh_token] = OutlookToken(token, time.monotonic() + expires_in)

    def _do_xoauth2(self, server: smtplib.SMTP, email: str, access_token: str):
        auth_string = f"user={email}\1auth=Bearer {access_token}\1\1"
        return server.docmd("AUTH XOAUTH2", base64.b64encode(auth_string.encode()).decode())
