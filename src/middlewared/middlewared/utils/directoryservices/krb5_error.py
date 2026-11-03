from enum import IntEnum

# ERROR_TABLE_BASE_krb5 in krb5.h, as an unsigned 32-bit GSSAPI minor status
KRB5_ERROR_TABLE_BASE = 0x96C73A00


# Offsets in the MIT krb5 error table (krb5_err.et), without the KRB5PLACEHOLD_* entries
class KRB5ErrCode(IntEnum):
    KRB5KDC_ERR_NONE = 0  # No error
    KRB5KDC_ERR_NAME_EXP = 1  # Client's entry in database has expired
    KRB5KDC_ERR_SERVICE_EXP = 2  # Server's entry in database has expired
    KRB5KDC_ERR_BAD_PVNO = 3  # Requested protocol version not supported
    KRB5KDC_ERR_C_OLD_MAST_KVNO = 4  # Client's key is encrypted in an old master key
    KRB5KDC_ERR_S_OLD_MAST_KVNO = 5  # Server's key is encrypted in an old master key
    KRB5KDC_ERR_C_PRINCIPAL_UNKNOWN = 6  # Client not found in Kerberos database
    KRB5KDC_ERR_S_PRINCIPAL_UNKNOWN = 7  # Server not found in Kerberos database
    KRB5KDC_ERR_PRINCIPAL_NOT_UNIQUE = 8  # Principal has multiple entries in Kerberos database
    KRB5KDC_ERR_NULL_KEY = 9  # Client or server has a null key
    KRB5KDC_ERR_CANNOT_POSTDATE = 10  # Ticket is ineligible for postdating
    KRB5KDC_ERR_NEVER_VALID = 11  # Requested effective lifetime is negative or too short
    KRB5KDC_ERR_POLICY = 12  # KDC policy rejects request
    KRB5KDC_ERR_BADOPTION = 13  # KDC can't fulfill requested option
    KRB5KDC_ERR_ETYPE_NOSUPP = 14  # KDC has no support for encryption type
    KRB5KDC_ERR_SUMTYPE_NOSUPP = 15  # KDC has no support for checksum type
    KRB5KDC_ERR_PADATA_TYPE_NOSUPP = 16  # KDC has no support for padata type
    KRB5KDC_ERR_TRTYPE_NOSUPP = 17  # KDC has no support for transited type
    KRB5KDC_ERR_CLIENT_REVOKED = 18  # Clients credentials have been revoked
    KRB5KDC_ERR_SERVICE_REVOKED = 19  # Credentials for server have been revoked
    KRB5KDC_ERR_TGT_REVOKED = 20  # TGT has been revoked
    KRB5KDC_ERR_CLIENT_NOTYET = 21  # Client not yet valid - try again later
    KRB5KDC_ERR_SERVICE_NOTYET = 22  # Server not yet valid - try again later
    KRB5KDC_ERR_KEY_EXP = 23  # Password has expired
    KRB5KDC_ERR_PREAUTH_FAILED = 24  # Preauthentication failed
    KRB5KDC_ERR_PREAUTH_REQUIRED = 25  # Additional pre-authentication required
    KRB5KDC_ERR_SERVER_NOMATCH = 26  # Requested server and ticket don't match
    KRB5KDC_ERR_MUST_USE_USER2USER = 27  # Server principal valid for user2user only
    KRB5KDC_ERR_PATH_NOT_ACCEPTED = 28  # KDC policy rejects transited path
    KRB5KDC_ERR_SVC_UNAVAILABLE = 29  # A service is not available that is required to process the request
    KRB5KRB_AP_ERR_BAD_INTEGRITY = 31  # Decrypt integrity check failed
    KRB5KRB_AP_ERR_TKT_EXPIRED = 32  # Ticket expired
    KRB5KRB_AP_ERR_TKT_NYV = 33  # Ticket not yet valid
    KRB5KRB_AP_ERR_REPEAT = 34  # Request is a replay
    KRB5KRB_AP_ERR_NOT_US = 35  # The ticket isn't for us
    KRB5KRB_AP_ERR_BADMATCH = 36  # Ticket/authenticator don't match
    KRB5KRB_AP_ERR_SKEW = 37  # Clock skew too great
    KRB5KRB_AP_ERR_BADADDR = 38  # Incorrect net address
    KRB5KRB_AP_ERR_BADVERSION = 39  # Protocol version mismatch
    KRB5KRB_AP_ERR_MSG_TYPE = 40  # Invalid message type
    KRB5KRB_AP_ERR_MODIFIED = 41  # Message stream modified
    KRB5KRB_AP_ERR_BADORDER = 42  # Message out of order
    KRB5KRB_AP_ERR_ILL_CR_TKT = 43  # Illegal cross-realm ticket
    KRB5KRB_AP_ERR_BADKEYVER = 44  # Key version is not available
    KRB5KRB_AP_ERR_NOKEY = 45  # Service key not available
    KRB5KRB_AP_ERR_MUT_FAIL = 46  # Mutual authentication failed
    KRB5KRB_AP_ERR_BADDIRECTION = 47  # Incorrect message direction
    KRB5KRB_AP_ERR_METHOD = 48  # Alternative authentication method required
    KRB5KRB_AP_ERR_BADSEQ = 49  # Incorrect sequence number in message
    KRB5KRB_AP_ERR_INAPP_CKSUM = 50  # Inappropriate type of checksum in message
    KRB5KRB_AP_PATH_NOT_ACCEPTED = 51  # Policy rejects transited path
    KRB5KRB_ERR_RESPONSE_TOO_BIG = 52  # Response too big for UDP, retry with TCP
    KRB5KRB_ERR_GENERIC = 60  # Generic error (see e-text)
    KRB5KRB_ERR_FIELD_TOOLONG = 61  # Field is too long for this implementation
    KRB5KDC_ERR_CLIENT_NOT_TRUSTED = 62  # Client not trusted
    KRB5KDC_ERR_KDC_NOT_TRUSTED = 63  # KDC not trusted
    KRB5KDC_ERR_INVALID_SIG = 64  # Invalid signature
    KRB5KDC_ERR_DH_KEY_PARAMETERS_NOT_ACCEPTED = 65  # Key parameters not accepted
    KRB5KDC_ERR_CERTIFICATE_MISMATCH = 66  # Certificate mismatch
    KRB5KRB_AP_ERR_NO_TGT = 67  # No ticket granting ticket
    KRB5KDC_ERR_WRONG_REALM = 68  # Realm not local to KDC
    KRB5KRB_AP_ERR_USER_TO_USER_REQUIRED = 69  # User to user required
    KRB5KDC_ERR_CANT_VERIFY_CERTIFICATE = 70  # Can't verify certificate
    KRB5KDC_ERR_INVALID_CERTIFICATE = 71  # Invalid certificate
    KRB5KDC_ERR_REVOKED_CERTIFICATE = 72  # Revoked certificate
    KRB5KDC_ERR_REVOCATION_STATUS_UNKNOWN = 73  # Revocation status unknown
    KRB5KDC_ERR_REVOCATION_STATUS_UNAVAILABLE = 74  # Revocation status unavailable
    KRB5KDC_ERR_CLIENT_NAME_MISMATCH = 75  # Client name mismatch
    KRB5KDC_ERR_KDC_NAME_MISMATCH = 76  # KDC name mismatch
    KRB5KDC_ERR_INCONSISTENT_KEY_PURPOSE = 77  # Inconsistent key purpose
    KRB5KDC_ERR_DIGEST_IN_CERT_NOT_ACCEPTED = 78  # Digest in certificate not accepted
    KRB5KDC_ERR_PA_CHECKSUM_MUST_BE_INCLUDED = 79  # Checksum must be included
    KRB5KDC_ERR_DIGEST_IN_SIGNED_DATA_NOT_ACCEPTED = 80  # Digest in signed-data not accepted
    KRB5KDC_ERR_PUBLIC_KEY_ENCRYPTION_NOT_SUPPORTED = 81  # Public key encryption not supported
    KRB5KRB_AP_ERR_IAKERB_KDC_NOT_FOUND = 85  # The IAKERB proxy could not find a KDC
    KRB5KRB_AP_ERR_IAKERB_KDC_NO_RESPONSE = 86  # The KDC did not respond to the IAKERB proxy
    KRB5KDC_ERR_PREAUTH_EXPIRED = 90  # Preauthentication expired
    KRB5KDC_ERR_MORE_PREAUTH_DATA_REQUIRED = 91  # More preauthentication data is required
    KRB5KDC_ERR_UNKNOWN_CRITICAL_FAST_OPTION = 93  # An unsupported critical FAST option was requested
    KRB5KDC_ERR_NO_ACCEPTABLE_KDF = 100  # No acceptable KDF offered
    KRB5_ERR_RCSID = 128  # (RCS Id string for the krb5 error table)
    KRB5_LIBOS_BADLOCKFLAG = 129  # Invalid flag for file lock mode
    KRB5_LIBOS_CANTREADPWD = 130  # Cannot read password
    KRB5_LIBOS_BADPWDMATCH = 131  # Password mismatch
    KRB5_LIBOS_PWDINTR = 132  # Password read interrupted
    KRB5_PARSE_ILLCHAR = 133  # Illegal character in component name
    KRB5_PARSE_MALFORMED = 134  # Malformed representation of principal
    KRB5_CONFIG_CANTOPEN = 135  # Can't open/find Kerberos configuration file
    KRB5_CONFIG_BADFORMAT = 136  # Improper format of Kerberos configuration file
    KRB5_CONFIG_NOTENUFSPACE = 137  # Insufficient space to return complete information
    KRB5_BADMSGTYPE = 138  # Invalid message type specified for encoding
    KRB5_CC_BADNAME = 139  # Credential cache name malformed
    KRB5_CC_UNKNOWN_TYPE = 140  # Unknown credential cache type
    KRB5_CC_NOTFOUND = 141  # Matching credential not found
    KRB5_CC_END = 142  # End of credential cache reached
    KRB5_NO_TKT_SUPPLIED = 143  # Request did not supply a ticket
    KRB5KRB_AP_WRONG_PRINC = 144  # Wrong principal in request
    KRB5KRB_AP_ERR_TKT_INVALID = 145  # Ticket has invalid flag set
    KRB5_PRINC_NOMATCH = 146  # Requested principal and ticket don't match
    KRB5_KDCREP_MODIFIED = 147  # KDC reply did not match expectations
    KRB5_KDCREP_SKEW = 148  # Clock skew too great in KDC reply
    KRB5_IN_TKT_REALM_MISMATCH = 149  # Client/server realm mismatch in initial ticket request
    KRB5_PROG_ETYPE_NOSUPP = 150  # Program lacks support for encryption type
    KRB5_PROG_KEYTYPE_NOSUPP = 151  # Program lacks support for key type
    KRB5_WRONG_ETYPE = 152  # Requested encryption type not used in message
    KRB5_PROG_SUMTYPE_NOSUPP = 153  # Program lacks support for checksum type
    KRB5_REALM_UNKNOWN = 154  # Cannot find KDC for requested realm
    KRB5_SERVICE_UNKNOWN = 155  # Kerberos service unknown
    KRB5_KDC_UNREACH = 156  # Cannot contact any KDC for requested realm
    KRB5_NO_LOCALNAME = 157  # No local name found for principal name
    KRB5_MUTUAL_FAILED = 158  # Mutual authentication failed
    KRB5_RC_TYPE_EXISTS = 159  # Replay cache type is already registered
    KRB5_RC_MALLOC = 160  # No more memory to allocate (in replay cache code)
    KRB5_RC_TYPE_NOTFOUND = 161  # Replay cache type is unknown
    KRB5_RC_UNKNOWN = 162  # Generic unknown RC error
    KRB5_RC_REPLAY = 163  # Message is a replay
    KRB5_RC_IO = 164  # Replay cache I/O operation failed
    KRB5_RC_NOIO = 165  # Replay cache type does not support non-volatile storage
    KRB5_RC_PARSE = 166  # Replay cache name parse/format error
    KRB5_RC_IO_EOF = 167  # End-of-file on replay cache I/O
    KRB5_RC_IO_MALLOC = 168  # No more memory to allocate (in replay cache I/O code)
    KRB5_RC_IO_PERM = 169  # Permission denied in replay cache code
    KRB5_RC_IO_IO = 170  # I/O error in replay cache i/o code
    KRB5_RC_IO_UNKNOWN = 171  # Generic unknown RC/IO error
    KRB5_RC_IO_SPACE = 172  # Insufficient system space to store replay information
    KRB5_TRANS_CANTOPEN = 173  # Can't open/find realm translation file
    KRB5_TRANS_BADFORMAT = 174  # Improper format of realm translation file
    KRB5_LNAME_CANTOPEN = 175  # Can't open/find lname translation database
    KRB5_LNAME_NOTRANS = 176  # No translation available for requested principal
    KRB5_LNAME_BADFORMAT = 177  # Improper format of translation database entry
    KRB5_CRYPTO_INTERNAL = 178  # Cryptosystem internal error
    KRB5_KT_BADNAME = 179  # Key table name malformed
    KRB5_KT_UNKNOWN_TYPE = 180  # Unknown Key table type
    KRB5_KT_NOTFOUND = 181  # Key table entry not found
    KRB5_KT_END = 182  # End of key table reached
    KRB5_KT_NOWRITE = 183  # Cannot write to specified key table
    KRB5_KT_IOERR = 184  # Error writing to key table
    KRB5_NO_TKT_IN_RLM = 185  # Cannot find ticket for requested realm
    KRB5DES_BAD_KEYPAR = 186  # DES key has bad parity
    KRB5DES_WEAK_KEY = 187  # DES key is a weak key
    KRB5_BAD_ENCTYPE = 188  # Bad encryption type
    KRB5_BAD_KEYSIZE = 189  # Key size is incompatible with encryption type
    KRB5_BAD_MSIZE = 190  # Message size is incompatible with encryption type
    KRB5_CC_TYPE_EXISTS = 191  # Credentials cache type is already registered.
    KRB5_KT_TYPE_EXISTS = 192  # Key table type is already registered.
    KRB5_CC_IO = 193  # Credentials cache I/O operation failed
    KRB5_FCC_PERM = 194  # Credentials cache file permissions incorrect
    KRB5_FCC_NOFILE = 195  # No credentials cache found
    KRB5_FCC_INTERNAL = 196  # Internal credentials cache error
    KRB5_CC_WRITE = 197  # Error writing to credentials cache
    KRB5_CC_NOMEM = 198  # No more memory to allocate (in credentials cache code)
    KRB5_CC_FORMAT = 199  # Bad format in credentials cache
    KRB5_CC_NOT_KTYPE = 200  # No credentials found with supported encryption types
    KRB5_INVALID_FLAGS = 201  # Invalid KDC option combination (library internal error) [for dual tgt library calls]
    KRB5_NO_2ND_TKT = 202  # Request missing second ticket [for dual tgt library calls]
    KRB5_NOCREDS_SUPPLIED = 203  # No credentials supplied to library routine
    KRB5_SENDAUTH_BADAUTHVERS = 204  # Bad sendauth version was sent
    KRB5_SENDAUTH_BADAPPLVERS = 205  # Bad application version was sent (via sendauth)
    KRB5_SENDAUTH_BADRESPONSE = 206  # Bad response (during sendauth exchange)
    KRB5_SENDAUTH_REJECTED = 207  # Server rejected authentication (during sendauth exchange)
    KRB5_PREAUTH_BAD_TYPE = 208  # Unsupported preauthentication type
    KRB5_PREAUTH_NO_KEY = 209  # Required preauthentication key not supplied
    KRB5_PREAUTH_FAILED = 210  # Generic preauthentication failure
    KRB5_RCACHE_BADVNO = 211  # Unsupported replay cache format version number
    KRB5_CCACHE_BADVNO = 212  # Unsupported credentials cache format version number
    KRB5_KEYTAB_BADVNO = 213  # Unsupported key table format version number
    KRB5_PROG_ATYPE_NOSUPP = 214  # Program lacks support for address type
    KRB5_RC_REQUIRED = 215  # Message replay detection requires rcache parameter
    KRB5_ERR_BAD_HOSTNAME = 216  # Hostname cannot be canonicalized
    KRB5_ERR_HOST_REALM_UNKNOWN = 217  # Cannot determine realm for host
    KRB5_SNAME_UNSUPP_NAMETYPE = 218  # Conversion to service principal undefined for name type
    KRB5KRB_AP_ERR_V4_REPLY = 219  # Initial Ticket response appears to be Version 4 error
    KRB5_REALM_CANT_RESOLVE = 220  # Cannot resolve KDC for requested realm
    KRB5_TKT_NOT_FORWARDABLE = 221  # Requesting ticket can't get forwardable tickets
    KRB5_FWD_BAD_PRINCIPAL = 222  # Bad principal name while trying to forward credentials
    KRB5_GET_IN_TKT_LOOP = 223  # Looping detected inside krb5_get_in_tkt
    KRB5_CONFIG_NODEFREALM = 224  # Configuration file does not specify default realm
    KRB5_SAM_UNSUPPORTED = 225  # Bad SAM flags in obtain_sam_padata
    KRB5_SAM_INVALID_ETYPE = 226  # Invalid encryption type in SAM challenge
    KRB5_SAM_NO_CHECKSUM = 227  # Missing checksum in SAM challenge
    KRB5_SAM_BAD_CHECKSUM = 228  # Bad checksum in SAM challenge
    KRB5_KT_NAME_TOOLONG = 229  # Keytab name too long
    KRB5_KT_KVNONOTFOUND = 230  # Key version number for principal in key table is incorrect
    KRB5_APPL_EXPIRED = 231  # This application has expired
    KRB5_LIB_EXPIRED = 232  # This Krb5 library has expired
    KRB5_CHPW_PWDNULL = 233  # New password cannot be zero length
    KRB5_CHPW_FAIL = 234  # Password change failed
    KRB5_KT_FORMAT = 235  # Bad format in keytab
    KRB5_NOPERM_ETYPE = 236  # Encryption type not permitted
    KRB5_CONFIG_ETYPE_NOSUPP = 237  # No supported encryption types (config file error?)
    KRB5_OBSOLETE_FN = 238  # Program called an obsolete, deleted function
    KRB5_EAI_FAIL = 239  # unknown getaddrinfo failure
    KRB5_EAI_NODATA = 240  # no data available for host/domain name
    KRB5_EAI_NONAME = 241  # host/domain name not found
    KRB5_EAI_SERVICE = 242  # service name unknown
    KRB5_ERR_NUMERIC_REALM = 243  # Cannot determine realm for numeric host address
    KRB5_ERR_BAD_S2K_PARAMS = 244  # Invalid key generation parameters from KDC
    KRB5_ERR_NO_SERVICE = 245  # service not available
    KRB5_CC_READONLY = 246  # Ccache function not supported: read-only ccache type
    KRB5_CC_NOSUPP = 247  # Ccache function not supported: not implemented
    KRB5_DELTAT_BADFORMAT = 248  # Invalid format of Kerberos lifetime or clock skew string
    KRB5_PLUGIN_NO_HANDLE = 249  # Supplied data not handled by this plugin
    KRB5_PLUGIN_OP_NOTSUPP = 250  # Plugin does not support the operation
    KRB5_ERR_INVALID_UTF8 = 251  # Invalid UTF-8 string
    KRB5_ERR_FAST_REQUIRED = 252  # FAST protected pre-authentication required but not supported by KDC
    KRB5_LOCAL_ADDR_REQUIRED = 253  # Auth context must contain local address
    KRB5_REMOTE_ADDR_REQUIRED = 254  # Auth context must contain remote address
    KRB5_TRACE_NOSUPP = 255  # Tracing unsupported


class KRB5Error(Exception):
    def __init__(
        self,
        gss_major: int,
        gss_minor: int,
        errmsg: str
    ):
        """
        KRB5Error exception is a wrapper around generic GSSAPI errors to
        provide more explicit guidance to areas of code that are dealing
        specifically with kerberos tickets.

        gss_major : major error code from GSSAPI exception
        gss_minor : minor error code from GSSAPI exception
        err_msg : human-readable message from GSSAPI exception (parses the
        major and minor codes and is produced by `gen_message()` method in
        exception.

        WARNING: krb5_code is None when gss_minor is not a code in the krb5
        error table. GSSAPI reports errno values (for example EDQUOT storing a
        ticket in the keyring ccache) and its own synthetic minor codes through
        the same exception. Every match on krb5_code must handle None.
        """
        self.gss_major_code = gss_major
        self.gss_minor_code = gss_minor
        self.errmsg = errmsg
        self.krb5_code: KRB5ErrCode | None = None
        if (gss_minor & 0xFFFFFF00) == KRB5_ERROR_TABLE_BASE:
            try:
                self.krb5_code = KRB5ErrCode(gss_minor & 0xFF)
            except ValueError:
                pass
        super().__init__(gss_major, gss_minor, errmsg)

    def __str__(self) -> str:
        if self.krb5_code is None:
            return self.errmsg
        return f'[{self.krb5_code.name}] {self.errmsg}'
