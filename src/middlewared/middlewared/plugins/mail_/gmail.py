import base64

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

from middlewared.service import private, Service


class GmailService:
    def __init__(self, config):
        self.config = config

        credentials = Credentials.from_authorized_user_info(config["oauth"])
        self.service = build("gmail", "v1", credentials=credentials)

    def __eq__(self, other):
        return isinstance(other, GmailService) and self.config["oauth"] == other.config["oauth"]

    def close(self):
        self.service.close()


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
    def gmail_send(self, message, config):
        gmail_service = self.middleware.call_sync("mail.gmail_build_service", config)
        if gmail_service == self.gmail_service:
            # Use existing gmail service if credentials match to avoid extra access token refresh
            gmail_service = self.gmail_service

        if gmail_service is None:
            raise RuntimeError("GMail service is not initialized")

        gmail_service.service.users().messages().send(userId="me", body={
            "raw": base64.urlsafe_b64encode(message.as_string().encode("ascii")).decode("ascii"),
        }).execute()

        if gmail_service != self.gmail_service:
            gmail_service.close()


async def setup(middleware):
    await middleware.call("mail.gmail_initialize")
