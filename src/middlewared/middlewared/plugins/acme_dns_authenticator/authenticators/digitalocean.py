from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from lexicon.client import Client
from lexicon.config import ConfigResolver

from middlewared.api.current import DigitalOceanSchemaArgs

from .base import Authenticator

if TYPE_CHECKING:
    from middlewared.main import Middleware


logger = logging.getLogger(__name__)


class _DigitalOceanLexiconClient:
    """Compatibility wrapper for DigitalOcean Lexicon client to match the old certbot interface"""

    def __init__(self, token: str, ttl: int) -> None:
        self.token = token
        self.ttl = ttl

    def _get_config(self, domain: str) -> Any:
        config_resolver_cls: Any = ConfigResolver
        resolver = config_resolver_cls()
        return resolver.with_dict({
            'provider_name': 'digitalocean',
            'domain': domain,
            'delegated': domain,  # Bypass Lexicon subdomain resolution
            'ttl': self.ttl,
            'digitalocean': {
                'auth_token': self.token,
            },
        })

    def add_txt_record(self, domain: str, validation_name: str, validation_content: str) -> None:
        """Add a TXT record using the DigitalOcean API via Lexicon"""
        with Client(self._get_config(domain)) as operations:
            operations.create_record(rtype='TXT', name=validation_name, content=validation_content)

    def del_txt_record(self, domain: str, validation_name: str, validation_content: str) -> None:
        """Delete a TXT record using the DigitalOcean API via Lexicon"""
        with Client(self._get_config(domain)) as operations:
            operations.delete_record(rtype='TXT', name=validation_name, content=validation_content)


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
        self.get_client().add_txt_record(domain, validation_name, validation_content)

    def get_client(self) -> _DigitalOceanLexiconClient:
        return _DigitalOceanLexiconClient(self.digitalocean_token, 600)

    def _cleanup(self, domain: str, validation_name: str, validation_content: str) -> None:
        self.get_client().del_txt_record(domain, validation_name, validation_content)
