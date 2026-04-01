from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING

import josepy as jose
import requests
from acme import client, messages
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa

import middlewared.sqlalchemy as sa
from middlewared.service import CRUDServicePart, ValidationErrors
from middlewared.service_exception import CallError

from .models import ACMERegistrationCreate, ACMERegistrationEntry

if TYPE_CHECKING:
    from middlewared.main import Middleware


class ACMERegistrationModel(sa.Model):
    __tablename__ = 'system_acmeregistration'

    id = sa.Column(sa.Integer(), primary_key=True)
    uri = sa.Column(sa.String(200))
    directory = sa.Column(sa.String(200), unique=True)
    tos = sa.Column(sa.String(200))
    new_account_uri = sa.Column(sa.String(200))
    new_nonce_uri = sa.Column(sa.String(200))
    new_order_uri = sa.Column(sa.String(200))
    revoke_cert_uri = sa.Column(sa.String(200))


class ACMERegistrationBodyModel(sa.Model):
    __tablename__ = 'system_acmeregistrationbody'

    id = sa.Column(sa.Integer(), primary_key=True)
    status = sa.Column(sa.String(10))
    key = sa.Column(sa.Text())
    acme_id = sa.Column(sa.ForeignKey('system_acmeregistration.id'), index=True)


class ACMERegistrationServicePart(CRUDServicePart[ACMERegistrationEntry]):
    _datastore = 'system.acmeregistration'
    _entry = ACMERegistrationEntry

    async def extend(self, data: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        data['body'] = {
            key: value for key, value in
            (await self.middleware.call(
                'datastore.query', 'system.acmeregistrationbody',
                [['acme', '=', data['id']]], {'get': True}
            )).items() if key != 'acme'
        }
        return data

    def do_create(self, data: ACMERegistrationCreate) -> ACMERegistrationEntry:
        # STEPS FOR CREATION
        # 1) CREATE KEY
        # 2) REGISTER CLIENT
        # 3) SAVE REGISTRATION OBJECT
        # 4) SAVE REGISTRATION BODY
        verrors = ValidationErrors()
        try:
            directory = _get_directory(self.middleware, data.acme_directory_uri)
        except CallError as e:
            verrors.add(
                'acme_registration_create.acme_directory_uri',
                f'System was unable to retrieve the directory with the specified acme_directory_uri: {e.errmsg}',
            )

        # Normalizing uri after directory call as let's encrypt staging api
        # does not accept a trailing slash right now
        acme_directory_uri = data.acme_directory_uri
        acme_directory_uri += '/' if acme_directory_uri[-1] != '/' else ''

        if not data.tos:
            verrors.add(
                'acme_registration_create.tos',
                'Please agree to the terms of service',
            )

        if self.run_coroutine(self.query([['directory', '=', acme_directory_uri]])):
            verrors.add(
                'acme_registration_create.acme_directory_uri',
                'A registration with the specified directory uri already exists',
            )

        verrors.check()

        key = jose.JWKRSA(key=rsa.generate_private_key(  # type: ignore[attr-defined]
            public_exponent=data.JWK_create.public_exponent,
            key_size=data.JWK_create.key_size,
            backend=default_backend(),
        ))
        acme_client = client.ClientV2(directory, client.ClientNetwork(key))
        register = acme_client.new_account(
            messages.NewRegistration.from_data(
                terms_of_service_agreed=True,
            )
        )

        registration_id: int = self.middleware.call_sync(
            'datastore.insert',
            self._datastore,
            {
                'uri': register.uri,
                'tos': register.terms_of_service or '',
                'new_account_uri': directory.newAccount,
                'new_nonce_uri': directory.newNonce,
                'new_order_uri': directory.newOrder,
                'revoke_cert_uri': directory.revokeCert,
                'directory': acme_directory_uri,
            },
        )

        self.middleware.call_sync(
            'datastore.insert',
            'system.acmeregistrationbody',
            {
                'status': register.body.status,
                'key': key.json_dumps(),
                'acme': registration_id,
            },
        )

        return self.get_instance__sync(registration_id)


def _get_directory(middleware: Middleware, acme_directory_uri: str) -> messages.Directory:
    middleware.call_sync('network.general.will_perform_activity', 'acme')

    try:
        acme_directory_uri = acme_directory_uri.rstrip('/')
        response = requests.get(acme_directory_uri).json()
        return messages.Directory({
            key: response[key] for key in ['newAccount', 'newNonce', 'newOrder', 'revokeCert']
        })
    except (requests.ConnectionError, requests.Timeout, json.JSONDecodeError, KeyError) as e:
        raise CallError(str(e))
