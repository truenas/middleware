import enum

from middlewared.utils import MIDDLEWARE_RUN_DIR


KRB_TKT_CHECK_INTERVAL = 1800

KRB5_CONF_FILE = '/etc/krb5.conf'


class KRB_Keytab(enum.Enum):
    SYSTEM = '/etc/krb5.keytab'


class krb5ccache(enum.Enum):
    SYSTEM = f'{MIDDLEWARE_RUN_DIR}/krb5cc_0'
    TEMP = f'{MIDDLEWARE_RUN_DIR}/krb5cc_middleware_temp'
    USER = f'{MIDDLEWARE_RUN_DIR}/krb5cc_'


class krb_tkt_flag(enum.Enum):
    FORWARDABLE = 'F'
    FORWARDED = 'f'
    PROXIABLE = 'P'
    PROXY = 'p'
    POSTDATEABLE = 'D'
    POSTDATED = 'd'
    RENEWABLE = 'R'
    INITIAL = 'I'
    INVALID = 'i'
    HARDWARE_AUTHENTICATED = 'H'
    PREAUTHENTICATED = 'A'
    TRANSIT_POLICY_CHECKED = 'T'
    OKAY_AS_DELEGATE = 'O'
    ANONYMOUS = 'a'


class KRB_AppDefaults(enum.Enum):
    FORWARDABLE = ('forwardable', 'boolean')
    PROXIABLE = ('proxiable', 'boolean')
    NO_ADDRESSES = ('no-addresses', 'boolean')
    TICKET_LIFETIME = ('ticket_lifetime', 'time')
    RENEW_LIFETIME = ('renew_lifetime', 'time')
    ENCRYPT = ('encrypt', 'boolean')
    FORWARD = ('forward', 'boolean')

    def __str__(self):
        return self.value[0]

    def parm(self):
        return self.value[0]


class KRB_LibDefaults(enum.Enum):
    DEFAULT_REALM = ('default_realm', 'realm')
    CANONICALIZE = ('canonicalize', 'boolean')
    CLOCKSKEW = ('clockskew', 'time')
    DEFAULT_CCACHE_NAME = ('default_ccache_name', 'ccname')
    DEFAULT_TGS_ENCTYPES = ('default_tgs_enctypes', 'etypes')
    DEFAULT_TKT_ENCTYPES = ('default_tkt_enctypes', 'etypes')
    DNS_CANONICALIZE_HOSTNAME = ('dns_canonicalize_hostname', 'string')
    DNS_LOOKUP_KDC = ('dns_lookup_kdc', 'boolean')
    DNS_LOOKUP_REALM = ('dns_lookup_realm', 'boolean')
    DNS_URI_LOOKUP = ('dns_uri_lookup', 'boolean')
    KDC_TIMESYNC = ('kdc_timesync', 'boolean')
    MAX_RETRIES = ('max_retries', 'number')
    TICKET_LIFETIME = ('ticket_lifetime', 'time')
    RENEW_LIFETIME = ('renew_lifetime', 'time')
    FORWARDABLE = ('forwardable', 'boolean')
    QUALIFY_SHORTNAME = ('qualify_shortname', 'string')
    PROXIABLE = ('proxiable', 'boolean')
    VERIFY_AP_REQ_NOFAIL = ('verify_ap_req_nofail', 'boolean')
    PERMITTED_ENCTYPES = ('permitted_enctypes', 'etypes')
    NOADDRESSES = ('noaddresses', 'boolan')
    EXTRA_ADDRESSES = ('extra_addresses', 'address')
    RDNS = ('rdns', 'boolean')

    def __str__(self):
        return self.value[0]

    def parm(self):
        return self.value[0]


class KRB_RealmProperty(enum.Enum):
    ADMIN_SERVER = ('admin_server', 'string')
    KDC = ('kdc', 'string')
    KPASSWD_SERVER = ('kpasswd_server', 'string')
    PRIMARY_KDC = ('primary_kdc', 'string')


class KRB_ETYPE(enum.Enum):
    DES_CBC_CRC = 'des-cbc-crc'  # weak
    DES_CBC_MD5 = 'des-cbc-md5'  # weak
    DES3_CBC_SHA1 = 'des3-cbc-sha1'  # deprecated
    ARCFOUR_HMAC = 'arcfour-hmac'  # weak
    ARCFOUR_HMAC_MD5 = 'arcfour-hmac-md5'  # deprecated
    AES128_CTS_HMAC_SHA1_96 = 'aes128-cts-hmac-sha1-96'
    AES256_CTS_HMAC_SHA1_96 = 'aes256-cts-hmac-sha1-96'
    AES256_CTS_HMAC_SHA256_128 = 'aes128-cts-hmac-sha256-128'
    AES256_CTS_HMAC_SHA384_192 = 'aes256-cts-hmac-sha384-192'
    CAMELLIA128_CTS_CMAC = 'camellia128-cts-cmac'
    CAMELLIA256_CTS_CMAC = 'camellia256-cts-cmac'
    AES = 'aes'  # Entire AES family
    CAMELLIA = 'camellia'  # Entire Camellia family
