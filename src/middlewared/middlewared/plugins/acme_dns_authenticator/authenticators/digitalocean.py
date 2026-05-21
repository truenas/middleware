from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import requests

from middlewared.api.current import DigitalOceanSchemaArgs

from .base import Authenticator

if TYPE_CHECKING:
    from middlewared.main import Middleware


logger = logging.getLogger(__name__)

DIGITALOCEAN_API = 'https://api.digitalocean.com/v2'


class _DigitalOceanClient:
    """Minimal DigitalOcean DNS API client for ACME TXT challenge records."""

    def __init__(self, token: str, ttl: int) -> None:
        self.ttl = ttl
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        })

    @staticmethod
    def _relative_name(domain: str, fqdn: str) -> str:
        name = fqdn.rstrip('.').lower()
        zone = domain.rstrip('.').lower()
        if name.endswith(zone):
            name = name[:-len(zone)].rstrip('.')
        return name

    def add_txt_record(self, domain: str, validation_name: str, validation_content: str) -> None:
        payload = {
            'type': 'TXT',
            'name': self._relative_name(domain, validation_name),
            'data': validation_content,
            'ttl': self.ttl,
        }
        response = self.session.post(f'{DIGITALOCEAN_API}/domains/{domain}/records', json=payload)
        response.raise_for_status()

    def del_txt_record(self, domain: str, validation_name: str, validation_content: str) -> None:
        relative_name = self._relative_name(domain, validation_name)
        next_url = f'{DIGITALOCEAN_API}/domains/{domain}/records'
        while next_url:
            response = self.session.get(next_url)
            response.raise_for_status()
            payload = response.json()
            for record in payload.get('domain_records', []):
                if (record.get('type') == 'TXT'
                        and record.get('name') == relative_name
                        and record.get('data') == validation_content):
                    delete_response = self.session.delete(
                        f'{DIGITALOCEAN_API}/domains/{domain}/records/{record["id"]}'
                    )
                    delete_response.raise_for_status()
            next_url = payload.get('links', {}).get('pages', {}).get('next')


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

    def get_client(self) -> _DigitalOceanClient:
        return _DigitalOceanClient(self.digitalocean_token, 600)

    def _cleanup(self, domain: str, validation_name: str, validation_content: str) -> None:
        self.get_client().del_txt_record(domain, validation_name, validation_content)
