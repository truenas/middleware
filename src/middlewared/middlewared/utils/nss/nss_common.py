import enum
import ctypes
import os

NSS_MODULES_DIR = '/usr/lib/x86_64-linux-gnu'
FILES_NSS_PATH = os.path.join(NSS_MODULES_DIR, 'libnss_files.so.2')
SSS_NSS_PATH = os.path.join(NSS_MODULES_DIR, 'libnss_sss.so.2')
WINBIND_NSS_PATH = os.path.join(NSS_MODULES_DIR, 'libnss_winbind.so.2')


class NssAccountFile(enum.Enum):
    USER = '/etc/passwd'
    GROUP = '/etc/group'


class NssReturnCode(enum.IntEnum):
    """ Possible NSS return codes, see /usr/include/nss.h """
    TRYAGAIN = -2
    UNAVAIL = -1
    NOTFOUND = 0
    SUCCESS = 1
    RETURN = 2


class NssModule(enum.Enum):
    """ Currently supported NSS modules """
    ALL = enum.auto()
    FILES = FILES_NSS_PATH
    SSS = SSS_NSS_PATH
    WINBIND = WINBIND_NSS_PATH


class NssOperation(enum.Enum):
    """ Currently supported NSS operations """
    GETGRNAM = 'getgrnam_r'
    GETGRGID = 'getgrgid_r'
    SETGRENT = 'setgrent'
    ENDGRENT = 'endgrent'
    GETGRENT = 'getgrent_r'
    GETPWNAM = 'getpwnam_r'
    GETPWUID = 'getpwuid_r'
    GETPWENT = 'getpwent_r'
    SETPWENT = 'setpwent'
    ENDPWENT = 'endpwent'


class NssError(Exception):
    def __init__(self, errno, nssop, return_code, module):
        self.errno = errno
        self.nssop = nssop.value
        self.return_code = return_code
        self.mod_name = module.name

    def __str__(self):
        errmsg = f'NSS operation {self.nssop} failed with errno {self.errno}: {self.return_code}'
        if self.mod_name != 'ALL':
            errmsg += f' on module [{self.mod_name.lower()}].'

        return errmsg


def get_nss_func(nss_op, nss_module):
    if nss_module == NssModule.ALL:
        raise ValueError('ALL module may not be explicitly used')

    lib = ctypes.CDLL(nss_module.value, use_errno=True)
    return getattr(lib, f'_nss_{nss_module.name.lower()}_{nss_op.value}')
