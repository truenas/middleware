import enum
from middlewared.utils import MIDDLEWARE_RUN_DIR
from middlewared.utils.directoryservices.krb5_constants import SAMBA_KEYTAB_DIR


NETIF_COMPLETE_SENTINEL = f"{MIDDLEWARE_RUN_DIR}/ix-netif-complete"
CONFIGURED_SENTINEL = '/var/run/samba/.configured'
SMB_AUDIT_DEFAULTS = {'enable': False, 'watch_list': [], 'ignore_list': []}


class SMBCmd(enum.Enum):
    """ Shell commands related to samba that may be used by backend. """
    NET = 'net'
    PDBEDIT = 'pdbedit'
    SHARESEC = 'sharesec'
    SMBCACLS = 'smbcacls'
    SMBCONTROL = 'smbcontrol'
    SMBPASSWD = 'smbpasswd'
    STATUS = 'smbstatus'
    WBINFO = 'wbinfo'


class SMBEncryption(enum.Enum):
    """ SMB server encryption options """
    DEFAULT = 'default'
    NEGOTIATE = 'if_required'
    DESIRED = 'desired'
    REQUIRED = 'required'


class SMBBuiltin(enum.Enum):
    """ Class for SMB builtin accounts that have special local groups. """
    ADMINISTRATORS = ('builtin_administrators', 'S-1-5-32-544')
    GUESTS = ('builtin_guests', 'S-1-5-32-546')
    USERS = ('builtin_users', 'S-1-5-32-545')

    @property
    def nt_name(self):
        """ name of account as it appears to SMB clients. """
        return self.value[0][8:].capitalize()

    @property
    def sid(self):
        """ SID value of builtin. """
        return self.value[1]

    @property
    def rid(self):
        """ RID value of builtin """
        return int(self.value[1].split('-')[-1])

    @property
    def unix_groups(self):
        """ Unix groups used by SMB builtins """
        return [x.value[0] for x in SMBBuiltin]

    @property
    def sids(self):
        """ SIDS consumed by these builtins """
        return [x.value[1] for x in SMBBuiltin]

    @classmethod
    def by_rid(cls, rid):
        """ Convert RID to SMB builtin """
        for x in SMBBuiltin:
            if x.value[1].endswith(str(rid)):
                return x

        return None


class SMBPath(enum.Enum):
    """ SMB related paths. This is consumed by smb.configure """
    GLOBALCONF = ('/etc/smb4.conf', 0o644, False)
    STUBCONF = ('/usr/local/etc/smb4.conf', 0o644, False)
    SHARECONF = ('/etc/smb4_share.conf', 0o755, False)
    STATEDIR = ('/var/db/system/samba4', 0o755, True)
    PRIVATEDIR = ('/var/db/system/samba4/private', 0o700, True)
    KEYTABDIR = (SAMBA_KEYTAB_DIR, 0o700, True)
    LEGACYSTATE = ('/root/samba', 0o755, True)
    LEGACYPRIVATE = ('/root/samba/private', 0o700, True)
    CACHE_DIR = ('/var/run/samba-cache', 0o755, True)
    PASSDB_DIR = ('/var/run/samba-cache/private', 0o700, True)
    MSG_SOCK = ('/var/db/system/samba4/private/msg.sock', 0o700, False)
    RUNDIR = ('/var/run/samba', 0o755, True)
    LOCKDIR = ('/var/run/samba-lock', 0o755, True)
    LOGDIR = ('/var/log/samba4', 0o755, True)
    IPCSHARE = ('/tmp', 0o1777, True)
    WINBINDD_PRIVILEGED = ('/var/db/system/samba4/winbindd_privileged', 0o750, True)

    @property
    def mode(self):
        """ Permissions that file / directory should have. """
        return self.value[1]

    @property
    def is_dir(self):
        """ Boolean indicating whether this is a directory. """
        return self.value[2]

    @property
    def path(self):
        """ Absolute path for file / directory """
        return self.value[0]


class SMBShareField(enum.StrEnum):
    """ Fields that are used for SMB shares. This is used to make it easier for
    linter to pick up typos. """
    PURPOSE = 'purpose'
    PATH = 'path'
    PATH_SUFFIX = 'path_suffix'
    HOME = 'home'
    NAME = 'name'
    COMMENT = 'comment'
    RO = 'readonly'
    BROWSEABLE = 'browsable'
    RECYCLE = 'recyclebin'
    GUESTOK = 'guestok'
    HOSTSALLOW = 'hostsallow'
    HOSTSDENY = 'hostsdeny'
    AUX = 'auxsmbconf'
    ABE = 'access_based_share_enumeration'
    ACL = 'acl'
    DURABLEHANDLE = 'durablehandle'
    STREAMS = 'streams'
    TIMEMACHINE = 'timemachine'
    TIMEMACHINE_QUOTA = 'timemachine_quota'
    SHADOWCOPY = 'shadowcopy'
    FSRVP = 'fsrvp'
    ENABLED = 'enabled'
    LOCKED = 'locked'
    AFP = 'afp'
    AUDIT = 'audit'
    AUDIT_ENABLE = 'enable'
    AUDIT_WATCH_LIST = 'watch_list'
    AUDIT_IGNORE_LIST = 'ignore_list'
    AUTO_QUOTA = 'auto_quota'
    AUTO_SNAP = 'auto_snapshot'
    AUTO_DS = 'auto_dataset_creation'
    WORM_GRACE = 'grace_period'
    AAPL_MANGLING = 'aapl_name_mangling'
    DS_NAMING_SCHEMA = 'dataset_naming_schema'
    REMOTE_PATH = 'remote_path'
    VUID = 'vuid'
    OPTS = 'options'


LEGACY_SHARE_FIELDS = frozenset([
    SMBShareField.PATH_SUFFIX, SMBShareField.HOME, SMBShareField.RECYCLE, SMBShareField.GUESTOK,
    SMBShareField.HOSTSALLOW, SMBShareField.HOSTSDENY, SMBShareField.AUX, SMBShareField.ACL,
    SMBShareField.DURABLEHANDLE, SMBShareField.STREAMS, SMBShareField.TIMEMACHINE,
    SMBShareField.TIMEMACHINE_QUOTA, SMBShareField.SHADOWCOPY, SMBShareField.FSRVP,
    SMBShareField.AFP,
])
