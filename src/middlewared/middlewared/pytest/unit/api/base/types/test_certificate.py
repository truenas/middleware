from cryptography import x509

from middlewared.api.base.types.certificate import EKU_OID


def test_eku_oid():
    assert set(EKU_OID.__members__.keys()) == {i for i in dir(x509.oid.ExtendedKeyUsageOID) if not i.startswith("__")}
