from enum import Enum

from cryptography import x509

__all__ = ['EKU_OID']

EKU_OID = Enum('EKU_OID', {i: i for i in dir(x509.oid.ExtendedKeyUsageOID) if not i.startswith('__')})
