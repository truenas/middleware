
# To use this:
# from . import Avatar
# os_type = Avatar()

# We may want to have more
# platform-specific stuff.

_os_type = "FreeNAS"
UPDATE_SERVER = "http://beta-update.freenas.org/" + _os_type

# For signature verification
ROOT_CA_FILE = "/usr/local/share/certs/iX-CA.pem"
UPDATE_CERT_FILE = "/usr/local/share/certs/freenas-update.pem"
VERIFIER_HELPER = "/usr/local/libexec/verify_signature"
SIGNATURE_FAILURE = False

try:
    import sys
    sys.path.append("/usr/local/www")
    from freenasUI.common.system import get_sw_name
    _os_type = get_sw_name()
    UPDATE_SERVER = "http://beta-update.freenas.org/" + _os_type
except:
    pass

def Avatar():
    return _os_type

