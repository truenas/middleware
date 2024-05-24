import enum

MAX_SERVER_TIME_OFFSET = 180

DEFAULT_SITE_NAME = 'Default-First-Site-Name'
MACHINE_ACCOUNT_KT_NAME = 'AD_MACHINE_ACCOUNT'


class ADUserAccountControl(enum.IntFlag):
    """
    see MS-ADTS section 2.2.16

    This is currently used to parse machine account UAC flags
    In the future it will also be used to parse user accounts
    when authorizing user-based AD api keys.
    """
    ACCOUNTDISABLE = 0x0002  # the user account is disabled
    HOMEDIR_REQUIRED = 0x0008  # home folder is required
    LOCKOUT = 0x0008  # account is temporarily locked out
    PASSWD_NOTREQD = 0x0010  # password-length policy  does not apply to user
    PASSWD_CANT_CHANGE = 0x0040  # user can't change password
    ENCRYPTED_TEXT_PWD_ALLOWED = 0x0080  # cleartext password is to be persisted
    TEMP_DUPLICATE_ACCOUNT = 0x0100  # account for users whose primary account is in another domain
    NORMAL_ACCOUNT = 0x0200  # default account type that represents a typical user
    INTERDOMAIN_TRUST_ACCOUNT = 0x0800  # permit to trust account for a system domain that trusts other domains
    WORKSTATION_TRUST_ACCOUNT = 0x1000  # computer account (domain member)
    SERVER_TRUST_ACCOUNT = 0x2000  # domain controller computer account
    DONT_EXPIRE_PASSWORD = 0x10000  # password should never expire
    SMARTCARD_REQUIRED = 0x40000  # user must logon by smartcard
    TRUSTED_FOR_DELEGATION = 0x80000  # used by kerberos protocol
    NOT_DELEGATED = 0x100000  # security context of user isn't delegated to a service
    USE_DES_KEY_ONLY = 0x200000  # used by kerberos protocol
    DONT_REQ_PREAUTH = 0x400000  # used by kerberos protocol
    PASSWORD_EXPIRED = 0x800000  # user password has expired
    TRUSTED_TO_AUTH_FOR_DELEGATION = 0x1000000  # used by kerberos protocol
    NO_AUTH_DATA_REQUIRED = 0x2000000  # used by kerberos protocol
    PARTIAL_SECRETS_ACCOUNT = 0x4000000  # account is a read-only domain controller computer account

    @classmethod
    def parse_flags(cls, flags_in: int) -> list:
        flags_list = []
        for flag in cls:
            if flags_in & int(flag):
                flags_list.append(flag.name)

        return flags_list


class ADEncryptionTypes(enum.IntFlag):
    """
    See MS-KILE section 2.2.7

    This is a decoder ring for the msDS-SupportedEncryptionTypes attribute
    for the AD computer account.
    """
    DES_CBC_CRC = 0x01
    DES_CBC_MD5 = 0x02
    ARCFOUR_HMAC = 0x04
    AES128_CTS_HMAC_SHA1_96 = 0x08
    AES256_CTS_HMAC_SHA1_96 = 0x10
    AES256_CTS_HMAC_SHA1_96_SK = 0x20  # enforce AES session keys when legacy ciphers in use.

    @classmethod
    def parse_flags(cls, flags_in: int) -> list:
        if flags_in == 0:
            # It is technically possible for sysadmin to edit the supported
            # enctypes for our computer object and set SupportedEncTypes to `0`.
            # This is undefined, but according to some MS documentation defaults
            # to RC4_HMAC. This behavior has been observed in user bug ticket.
            return [cls.ARCFOUR_HMAC.name]

        flags_list = []

        for flag in cls:
            if flags_in & int(flag):
                flags_list.append(flag.name)

        return flags_list
