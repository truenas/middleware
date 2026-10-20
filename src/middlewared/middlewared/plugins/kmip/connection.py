# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from __future__ import annotations

import contextlib
from logging import Logger
from typing import TYPE_CHECKING, Any, Iterator

from kmip.core import enums
from kmip.pie.client import ProxyKmipClient
from kmip.pie.exceptions import ClientConnectionFailure, ClientConnectionNotOpen, KmipOperationFailure
from kmip.pie.objects import SecretData

from middlewared.alert.source.kmip import KMIPConnectionFailedAlert
from middlewared.service import CallError
from middlewared.utils.crypto import ssl_uuid4

if TYPE_CHECKING:
    from middlewared.service import ServiceContext


@contextlib.contextmanager
def kmip_connection(context: ServiceContext, data: dict[str, Any] | None = None) -> Iterator[ProxyKmipClient]:
    context.middleware.call_sync('network.general.will_perform_activity', 'kmip')

    data = data or {}
    mapping = {
        'hostname': 'server',
        'port': 'port',
        'cert': 'cert',
        'key': 'cert_key',
        'ca': 'ca',
        'ssl_version': 'ssl_version'
    }
    try:
        with ProxyKmipClient(**{k: data[v] for k, v in mapping.items() if data.get(v)}) as conn:
            yield conn
    except (ClientConnectionFailure, ClientConnectionNotOpen, OSError) as e:
        raise CallError(f'Failed to connect to KMIP Server: {e}')


def test_connection_impl(context: ServiceContext, data: dict[str, Any] | None = None) -> dict[str, Any]:
    # Test if we are able to connect to the KMIP Server
    try:
        with kmip_connection(context, data):
            pass
    except Exception as e:
        return {'error': True, 'exception': str(e)}
    else:
        return {'error': False, 'exception': None}


def connection_config(context: ServiceContext, data: dict[str, Any] | None = None) -> dict[str, Any]:
    config = context.call_sync2(context.s.kmip.config).model_dump()
    config.update(data or {})
    cert = context.call_sync2(
        context.s.certificate.query, [['id', '=', config['certificate']]],
    )
    ca = context.call_sync2(
        context.s.certificate.query, [['id', '=', config['certificate_authority']]],
    )
    if not cert or not ca:
        raise CallError('Certificate/CA not setup correctly')
    return {
        **config,
        'cert': cert[0].certificate_path,
        'cert_key': cert[0].privatekey_path,
        'ca': ca[0].certificate_path,
    }


def test_connection(context: ServiceContext, data: dict[str, Any] | None = None, raise_alert: bool = False) -> bool:
    try:
        result = test_connection_impl(context, connection_config(context, data))
    except CallError as e:
        result = {'error': True, 'exception': str(e)}
    if result['error']:
        if raise_alert:
            config = context.call_sync2(context.s.kmip.config)
            context.call_sync2(
                context.s.alert.oneshot_create,
                KMIPConnectionFailedAlert(server=config.server or '', error=result['exception'])
            )
        return False
    else:
        return True


def delete_kmip_secret_data(context: ServiceContext, uid: str) -> bool:
    with kmip_connection(context, connection_config(context)) as conn:
        return revoke_and_destroy_key(uid, conn, context.middleware.logger)


def revoke_key(uid: str, conn: ProxyKmipClient) -> None:
    # Revoke key from the KMIP Server
    try:
        conn.revoke(enums.RevocationReasonCode.CESSATION_OF_OPERATION, uid)
    except KmipOperationFailure as e:
        raise CallError(f'Failed to revoke key: {e}')


def revoke_and_destroy_key(
    uid: str, conn: ProxyKmipClient, logger: Logger | None = None, key_id: str | None = None,
) -> bool:
    try:
        revoke_key(uid, conn)
    except Exception as e:
        if logger:
            logger.debug(f'Failed to revoke key for {key_id or uid}: {e}')
    try:
        destroy_key(uid, conn)
    except Exception as e:
        if logger:
            logger.debug(f'Failed to destroy key for {key_id or uid}: {e}')
        return False
    else:
        return True


def destroy_key(uid: str, conn: ProxyKmipClient) -> None:
    # Destroy key from the KMIP Server
    try:
        conn.destroy(uid)
    except KmipOperationFailure as e:
        raise CallError(f'Failed to destroy key: {e}')


def retrieve_secret_data(uid: str, conn: ProxyKmipClient) -> str:
    # Query key from the KMIP Server
    try:
        obj = conn.get(uid)
    except KmipOperationFailure as e:
        raise CallError(f'Failed to retrieve secret data: {e}')
    else:
        if not isinstance(obj, SecretData):
            raise CallError('Retrieved managed object is not secret data')
        decoded: str = obj.value.decode()
        return decoded


def register_secret_data(name: str, key: str, conn: ProxyKmipClient) -> str:
    # Create key on the KMIP Server
    secret_data = SecretData(key.encode(), enums.SecretDataType.PASSWORD, name=f'{name}-{str(ssl_uuid4())[:7]}')
    uid: str
    try:
        uid = conn.register(secret_data)
    except KmipOperationFailure as e:
        raise CallError(f'Failed to register key with KMIP server: {e}')
    else:
        try:
            conn.activate(uid)
        except KmipOperationFailure as e:
            error = f'Failed to activate key: {e}'
            try:
                destroy_key(uid, conn)
            except CallError as ce:
                error += f'\nFailed to destroy created key: {ce}'
            raise CallError(error)
        return uid
