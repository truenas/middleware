import contextlib
import socket

from kmip.core import enums
from kmip.pie.client import ProxyKmipClient
from kmip.pie.exceptions import ClientConnectionFailure, ClientConnectionNotOpen, KmipOperationFailure
from kmip.pie.objects import SecretData

from middlewared.service import CallError


class KMIPServerMixin:

    @contextlib.contextmanager
    def _connection(self, data=None):
        data = data or {}
        mapping = {'hostname': 'server', 'port': 'port', 'cert': 'cert', 'key': 'cert_key', 'ca': 'ca'}
        try:
            with ProxyKmipClient(**{k: data[v] for k, v in mapping.items() if data.get(k)}) as conn:
                yield conn
        except (ClientConnectionFailure, ClientConnectionNotOpen, socket.timeout) as e:
            raise CallError(f'Failed to connect to KMIP Server: {e}')

    def _test_connection(self, data=None):
        # Test if we are able to connect to the KMIP Server
        try:
            with self._connection(data):
                pass
        except Exception as e:
            return {'error': True, 'exception': str(e)}
        else:
            return {'error': False, 'exception': None}

    def _revoke_key(self, uid, conn):
        # Revoke key from the KMIP Server
        try:
            conn.revoke(enums.RevocationReasonCode.CESSATION_OF_OPERATION, uid)
        except KmipOperationFailure as e:
            raise CallError(f'Failed to revoke key: {e}')

    def _revoke_and_destroy_key(self, uid, conn):
        with contextlib.suppress(Exception):
            self._revoke_key(uid, conn)
        try:
            self._destroy_key(uid, conn)
        except Exception:
            return False
        else:
            return True

    def _destroy_key(self, uid, conn):
        # Destroy key from the KMIP Server
        try:
            conn.destroy(uid)
        except KmipOperationFailure as e:
            raise CallError(f'Failed to destroy key: {e}')

    def _retrieve_secret_data(self, uid, conn):
        # Query key from the KMIP Server
        try:
            obj = conn.get(uid)
        except KmipOperationFailure as e:
            raise CallError(f'Failed to retrieve secret data: {e}')
        else:
            if not isinstance(obj, SecretData):
                raise CallError('Retrieved managed object is not secret data')
            return obj.value.decode()

    def _register_secret_data(self, key, conn):
        # Create key on the KMIP Server
        secret_data = SecretData(key.encode(), enums.SecretDataType.PASSWORD)
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
                    self._destroy_key(uid, conn)
                except CallError as ce:
                    error += f'\nFailed to destroy created key: {ce}'
                raise CallError(error)
            return uid
