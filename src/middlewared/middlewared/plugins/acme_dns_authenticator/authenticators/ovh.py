from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from lexicon.client import Client
from lexicon.config import ConfigResolver

from middlewared.api.current import OVHSchemaArgs

from .base import Authenticator

if TYPE_CHECKING:
    from middlewared.main import Middleware


logger = logging.getLogger(__name__)


class _OVHLexiconClient:
    """Compatibility wrapper for OVH Lexicon client to match the old certbot interface"""

    def __init__(
        self, endpoint: str, application_key: str, application_secret: str, consumer_key: str, ttl: int,
    ) -> None:
        self.endpoint = endpoint
        self.application_key = application_key
        self.application_secret = application_secret
        self.consumer_key = consumer_key
        self.ttl = ttl

    def _get_config(self, domain: str) -> Any:
        config_resolver_cls: Any = ConfigResolver
        resolver = config_resolver_cls()
        return resolver.with_dict({
            "provider_name": "ovh",
            "domain": domain,
            "delegated": domain,  # Bypass Lexicon subdomain resolution
            "ttl": self.ttl,
            "ovh": {
                "auth_entrypoint": self.endpoint,
                "auth_application_key": self.application_key,
                "auth_application_secret": self.application_secret,
                "auth_consumer_key": self.consumer_key
            }
        })

    def add_txt_record(self, domain: str, validation_name: str, validation_content: str) -> None:
        """Add a TXT record using the OVH API via Lexicon"""
        with Client(self._get_config(domain)) as operations:
            operations.create_record(rtype="TXT", name=validation_name, content=validation_content)

    def del_txt_record(self, domain: str, validation_name: str, validation_content: str) -> None:
        """Delete a TXT record using the OVH API via Lexicon"""
        with Client(self._get_config(domain)) as operations:
            operations.delete_record(rtype="TXT", name=validation_name, content=validation_content)


class OVHAuthenticator(Authenticator):

    NAME = "OVH"
    PROPAGATION_DELAY = 60
    SCHEMA_MODEL = OVHSchemaArgs

    def initialize_credentials(self) -> None:
        self.application_key: str = self.attributes["application_key"]
        self.application_secret: str = self.attributes["application_secret"]
        self.consumer_key: str = self.attributes["consumer_key"]
        self.endpoint: str = self.attributes["endpoint"]

    @staticmethod
    async def validate_credentials(middleware: Middleware, data: dict[str, Any]) -> dict[str, Any]:
        return data

    def _perform(self, domain: str, validation_name: str, validation_content: str) -> None:
        self.get_client().add_txt_record(domain, validation_name, validation_content)

    def get_client(self) -> _OVHLexiconClient:
        return _OVHLexiconClient(
            self.endpoint, self.application_key, self.application_secret,
            self.consumer_key, 600,
        )

    def _cleanup(self, domain: str, validation_name: str, validation_content: str) -> None:
        self.get_client().del_txt_record(domain, validation_name, validation_content)
