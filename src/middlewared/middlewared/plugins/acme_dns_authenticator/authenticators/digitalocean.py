from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from certbot_dns_digitalocean._internal.dns_digitalocean import _DigitalOceanClient

from middlewared.api.current import DigitalOceanSchemaArgs

from .base import Authenticator

if TYPE_CHECKING:
    from middlewared.main import Middleware


logger = logging.getLogger(__name__)


class DigitalOceanAuthenticator(Authenticator):

    NAME = 'digitalocean'
    PROPAGATION_DELAY = 60
    SCHEMA_MODEL = DigitalOceanSchemaArgs

    def initialize_credentials(self) -> None:
        self.digitalocean_token: str = self.attributes['digitalocean_token']

    @staticmethod
    async def validate_credentials(middleware: Middleware, data: dict[str, Any]) -> dict[str, Any]:
        return data

    def _perform(self, domain: str, validation_name: str, validation_content: str) -> None:
        self.get_client().add_txt_record(domain, validation_name, validation_content, 600)

    def get_client(self) -> _DigitalOceanClient:
        return _DigitalOceanClient(self.digitalocean_token)

    def _cleanup(self, domain: str, validation_name: str, validation_content: str) -> None:
        self.get_client().del_txt_record(domain, validation_name, validation_content)
