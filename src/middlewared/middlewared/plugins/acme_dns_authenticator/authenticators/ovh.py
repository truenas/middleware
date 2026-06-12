from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

import requests

from middlewared.api.base.types.cloud import OVH_ENDPOINTS
from middlewared.api.current import OVHSchemaArgs

from .base import Authenticator

if TYPE_CHECKING:
    from middlewared.main import Middleware


logger = logging.getLogger(__name__)


class _OVHClient:
    """Minimal OVH DNS API client for ACME TXT challenge records.

    OVH signs every request with HMAC-SHA1 over a fixed-order payload; see
    https://github.com/ovh/python-ovh for the reference implementation.
    """

    def __init__(
        self, endpoint: str, application_key: str, application_secret: str,
        consumer_key: str, ttl: int,
    ) -> None:
        self.endpoint_api = OVH_ENDPOINTS[endpoint]
        self.application_key = application_key
        self.application_secret = application_secret
        self.consumer_key = consumer_key
        self.ttl = ttl
        self.session = requests.Session()
        self._time_delta: int | None = None

    def _sync_time(self) -> int:
        # OVH rejects requests whose timestamp drifts too far from server time
        if self._time_delta is None:
            server_time = self.session.get(f'{self.endpoint_api}/auth/time').json()
            self._time_delta = server_time - int(time.time())
        return self._time_delta

    def _request(
        self, method: str, path: str,
        data: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
    ) -> Any:
        time_delta = self._sync_time()
        url = self.endpoint_api + path
        body = json.dumps(data) if data is not None else ''
        timestamp = str(int(time.time()) + time_delta)

        # Signature is computed over the fully-resolved URL including query params
        signed_url = f'{url}?{urlencode(params)}' if params else url
        signature_payload = '+'.join([
            self.application_secret, self.consumer_key, method.upper(),
            signed_url, body, timestamp,
        ]).encode('utf-8')

        headers = {
            'X-Ovh-Application': self.application_key,
            'X-Ovh-Consumer': self.consumer_key,
            'X-Ovh-Timestamp': timestamp,
            'X-Ovh-Signature': '$1$' + hashlib.sha1(signature_payload).hexdigest(),
        }
        if data is not None:
            headers['Content-type'] = 'application/json'

        response = self.session.request(method, url, params=params, data=body, headers=headers)
        response.raise_for_status()
        return response.json() if response.text else None

    @staticmethod
    def _relative_name(domain: str, fqdn: str) -> str:
        name = fqdn.rstrip('.').lower()
        zone = domain.rstrip('.').lower()
        if name.endswith(zone):
            name = name[:-len(zone)].rstrip('.')
        return name

    def _find_record_ids(self, domain: str, sub_domain: str, content: str) -> list[int]:
        record_ids = self._request(
            'GET', f'/domain/zone/{domain}/record',
            params={'fieldType': 'TXT', 'subDomain': sub_domain},
        ) or []
        matching = []
        for record_id in record_ids:
            record = self._request('GET', f'/domain/zone/{domain}/record/{record_id}')
            if record and record.get('target') == content:
                matching.append(record_id)
        return matching

    def add_txt_record(self, domain: str, validation_name: str, validation_content: str) -> None:
        sub_domain = self._relative_name(domain, validation_name)
        if self._find_record_ids(domain, sub_domain, validation_content):
            return
        self._request('POST', f'/domain/zone/{domain}/record', data={
            'fieldType': 'TXT',
            'subDomain': sub_domain,
            'target': validation_content,
            'ttl': self.ttl,
        })
        self._request('POST', f'/domain/zone/{domain}/refresh')

    def del_txt_record(self, domain: str, validation_name: str, validation_content: str) -> None:
        sub_domain = self._relative_name(domain, validation_name)
        for record_id in self._find_record_ids(domain, sub_domain, validation_content):
            self._request('DELETE', f'/domain/zone/{domain}/record/{record_id}')
        self._request('POST', f'/domain/zone/{domain}/refresh')


class OVHAuthenticator(Authenticator):

    NAME = 'OVH'
    PROPAGATION_DELAY = 60
    SCHEMA_MODEL = OVHSchemaArgs

    def initialize_credentials(self) -> None:
        self.application_key: str = self.attributes['application_key']
        self.application_secret: str = self.attributes['application_secret']
        self.consumer_key: str = self.attributes['consumer_key']
        self.endpoint: str = self.attributes['endpoint']

    @staticmethod
    async def validate_credentials(middleware: Middleware, data: dict[str, Any]) -> dict[str, Any]:
        return data

    def _perform(self, domain: str, validation_name: str, validation_content: str) -> None:
        self.get_client().add_txt_record(domain, validation_name, validation_content)

    def get_client(self) -> _OVHClient:
        return _OVHClient(
            self.endpoint, self.application_key, self.application_secret,
            self.consumer_key, 600,
        )

    def _cleanup(self, domain: str, validation_name: str, validation_content: str) -> None:
        self.get_client().del_txt_record(domain, validation_name, validation_content)
