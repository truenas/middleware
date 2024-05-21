import enum

from middlewared.utils import MIDDLEWARE_RUN_DIR


KRB_TKT_CHECK_INTERVAL = 1800


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
    ALLOW_WEAK_CRYPTO = ('allow_weak_crypto', 'boolean')
    CLOCKSKEW = ('clockskew', 'time')
    KDC_TIMEOUT = ('kdc_timeout', 'time')
    DEFAULT_CC_TYPE = ('ccache_type', 'cctype')
    DEFAULT_CC_NAME = ('default_ccache_name', 'ccname')
    DEFAULT_ETYPES = ('default_etypes', 'etypes')
    DEFAULT_AS_ETYPES = ('default_as_etypes', 'etypes')
    DEFAULT_TGS_ETYPES = ('default_tgs_etypes', 'etypes')
    DEFAULT_ETYPES_DES = ('default_etypes_des', 'etypes')
    DEFAULT_KEYTAB_NAME = ('default_keytab_name', 'keytab')
    DNS_LOOKUP_KDC = ('dns_lookup_kdc', 'boolean')
    DNS_LOOKUP_REALM = ('dns_lookup_realm', 'boolean')
    KDC_TIMESYNC = ('kdc_timesync', 'boolean')
    MAX_RETRIES = ('max_retries', 'number')
    LARGE_MSG_SIZE = ('large_msg_size', 'number')
    TICKET_LIFETIME = ('ticket_lifetime', 'time')
    RENEW_LIFETIME = ('renew_lifetime', 'time')
    FORWARDABLE = ('forwardable', 'boolean')
    PROXIABLE = ('proxiable', 'boolean')
    VERIFY_AP_REQ_NOFAIL = ('verify_ap_req_nofail', 'boolean')
    WARN_PWEXPIRE = ('warn_pwexpire', 'time')
    HTTP_PROXY = ('http_proxy', 'proxy-spec')
    DNS_PROXY = ('dns_proxy', 'proxy-spec')
    EXTRA_ADDRESSES = ('extra_addresses', 'address')
    TIME_FORMAT = ('time_format', 'string')
    DATE_FORMAT = ('date_format', 'string')
    LOG_UTC = ('log_utc', 'boolean')
    SCAN_INTERFACES = ('scan_interfaces', 'boolean')
    FCACHE_VERSION = ('fcache_version', 'int')
    KRB4_GET_TICKETS = ('krb4_get_tickets', 'boolean')
    FCC_MIT_TICKETFLAGS = ('fcc-mit-ticketflags', 'boolean')
    RDNS = ('rdns', 'boolean')

    def __str__(self):
        return self.value[0]

    def parm(self):
        return self.value[0]


class KRB_ETYPE(enum.Enum):
    DES_CBC_CRC = 'des-cbc-crc'
    DES_CBC_MD4 = 'des-cbc-md4'
    DES_CBC_MD5 = 'des-cbc-md5'
    DES3_CBC_SHA1 = 'des3-cbc-sha1'
    ARCFOUR_HMAC_MD5 = 'arcfour-hmac-md5'
    AES128_CTS_HMAC_SHA1_96 = 'aes128-cts-hmac-sha1-96'
    AES256_CTS_HMAC_SHA1_96 = 'aes256-cts-hmac-sha1-96'
