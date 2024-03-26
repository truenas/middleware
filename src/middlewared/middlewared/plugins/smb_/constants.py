import enum
from bidict import bidict
from middlewared.utils import MIDDLEWARE_RUN_DIR


NETIF_COMPLETE_SENTINEL = f"{MIDDLEWARE_RUN_DIR}/ix-netif-complete"
CONFIGURED_SENTINEL = '/var/run/samba/.configured'
SMB_AUDIT_DEFAULTS = {'enable': False, 'watch_list': [], 'ignore_list': []}
INVALID_SHARE_NAME_CHARACTERS = {'%', '<', '>', '*', '?', '|', '/', '\\', '+', '=', ';', ':', '"', ',', '[', ']'}
RESERVED_SHARE_NAMES = ('global', 'printers', 'homes')

LOGLEVEL_MAP = bidict({
    '0': 'NONE',
    '1': 'MINIMUM',
    '2': 'NORMAL',
    '3': 'FULL',
    '10': 'DEBUG',
})


class SMBHAMODE(enum.IntEnum):
    """
    'standalone' - Not an HA system.
    'legacy' - Two samba instances simultaneously running on active and standby controllers with no shared state.
    'unified' - Single set of state files migrating between controllers. Single netbios name.
    """
    STANDALONE = 0
    UNIFIED = 2
    CLUSTERED = 3


class SMBCmd(enum.Enum):
    NET = 'net'
    PDBEDIT = 'pdbedit'
    SHARESEC = 'sharesec'
    SMBCACLS = 'smbcacls'
    SMBCONTROL = 'smbcontrol'
    SMBPASSWD = 'smbpasswd'
    STATUS = 'smbstatus'
    WBINFO = 'wbinfo'


class SMBBuiltin(enum.Enum):
    ADMINISTRATORS = ('builtin_administrators', 'S-1-5-32-544')
    GUESTS = ('builtin_guests', 'S-1-5-32-546')
    USERS = ('builtin_users', 'S-1-5-32-545')

    def unix_groups():
        return [x.value[0] for x in SMBBuiltin]

    def sids():
        return [x.value[1] for x in SMBBuiltin]

    def by_rid(rid):
        for x in SMBBuiltin:
            if x.value[1].endswith(str(rid)):
                return x

        return None


class SMBPath(enum.Enum):
    GLOBALCONF = ('/etc/smb4.conf', 0o755, False)
    STUBCONF = ('/usr/local/etc/smb4.conf', 0o755, False)
    SHARECONF = ('/etc/smb4_share.conf', 0o755, False)
    STATEDIR = ('/var/db/system/samba4', 0o755, True)
    PRIVATEDIR = ('/var/db/system/samba4/private', 0o700, True)
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

    def platform(self):
        return self.value[0]

    def mode(self):
        return self.value[1]

    def is_dir(self):
        return self.value[2]


class SMBSharePreset(enum.Enum):
    NO_PRESET = {"verbose_name": "No presets", "params": {
        'auxsmbconf': '',
    }, "cluster": False}
    DEFAULT_SHARE = {"verbose_name": "Default share parameters", "params": {
        'path_suffix': '',
        'home': False,
        'ro': False,
        'browsable': True,
        'timemachine': False,
        'recyclebin': False,
        'abe': False,
        'hostsallow': [],
        'hostsdeny': [],
        'aapl_name_mangling': False,
        'acl': True,
        'durablehandle': True,
        'shadowcopy': True,
        'streams': True,
        'fsrvp': False,
        'auxsmbconf': '',
    }, "cluster": False}
    TIMEMACHINE = {"verbose_name": "Basic time machine share", "params": {
        'path_suffix': '',
        'timemachine': True,
        'auxsmbconf': '',
    }, "cluster": False}
    ENHANCED_TIMEMACHINE = {"verbose_name": "Multi-user time machine", "params": {
        'path_suffix': '%U',
        'timemachine': True,
        'auxsmbconf': '\n'.join([
            'zfs_core:zfs_auto_create=true'
        ])
    }, "cluster": False}
    MULTI_PROTOCOL_NFS = {"verbose_name": "Multi-protocol (NFSv4/SMB) shares", "params": {
        'streams': True,
        'durablehandle': False,
        'auxsmbconf': '',
    }, "cluster": False}
    PRIVATE_DATASETS = {"verbose_name": "Private SMB Datasets and Shares", "params": {
        'path_suffix': '%U',
        'auxsmbconf': '\n'.join([
            'zfs_core:zfs_auto_create=true'
        ])
    }, "cluster": False}
    WORM_DROPBOX = {"verbose_name": "SMB WORM. Files become readonly via SMB after 5 minutes", "params": {
        'path_suffix': '',
        'auxsmbconf': '\n'.join([
            'worm:grace_period = 300',
        ])
    }, "cluster": False}
