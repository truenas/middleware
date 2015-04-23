
# To use this:
# from . import Avatar
# os_type = Avatar()

# We may want to have more
# platform-specific stuff.

# Sef likes this line a lot.
_os_type = "FreeNAS"
UPDATE_SERVER = "http://update.freenas.org/" + _os_type

# For signature verification
IX_CRL = "https://web.ixsystems.com/updates/ix_crl.pem"
DEFAULT_CA_FILE = "/usr/local/share/certs/ca-root-nss.crt"
IX_ROOT_CA_FILE = "/usr/local/share/certs/iX-CA.pem"
UPDATE_CERT_FILE = "/usr/local/share/certs/freenas-update.pem"
VERIFIER_HELPER = "/usr/local/libexec/verify_signature"
SIGNATURE_FAILURE = True

# TODO: Add FN10's equivalent of get_sw_name (for TN10 when applicable)


def Avatar():
    return _os_type
