import enum
import ctypes
import os

from collections import defaultdict


NSS_MODULES_DIR = '/usr/lib/x86_64-linux-gnu'
FILES_NSS_PATH = os.path.join(NSS_MODULES_DIR, 'libnss_files.so.2')
SSS_NSS_PATH = os.path.join(NSS_MODULES_DIR, 'libnss_sss.so.2')
WINBIND_NSS_PATH = os.path.join(NSS_MODULES_DIR, 'libnss_winbind.so.2')


class NSSModuleFN(defaultdict):
    """ Default dictionary containing references to C function pointers for a specific NSS module.
    Example: '_nss_files_getpwnam_r' """
    cddl = None
    module_name = None

    def __missing__(self, key):
        fn = getattr(self.cdll, f'_nss_{self.module_name}_{key}')
        self[key] = fn
        return fn


class NSSModuleCDLL(defaultdict):
    """ A default dictionary that holds references loaded shared libaries for the NSS modules above.
    For example, '/usr/lib/x86_64-linux-gnu/libnss_files.so.2'. The returned value is an NSSModuleFN
    that will hold references to lazy-initialized C function pointers."""
    def __missing__(self, key):
        mod, path = key.split('.', 1)
        cdll = ctypes.CDLL(path, use_errno=True)
        self[key] = NSSModuleFN()
        self[key].cdll = cdll
        self[key].module_name = mod.lower()
        return self[key]


NSSDICT = NSSModuleCDLL()


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


def get_nss_func(nss_op: NssOperation, nss_module: NssModule):
    """ Get the C function pointer for the particular NSS operation for the NSS module. The cache
    is lazy-initialized as different modules are used. Standalone servers will only ever use the
    files module. """
    if nss_module == NssModule.ALL:
        raise ValueError('ALL module may not be explicitly used')

    mod_ptr = NSSDICT[f'{nss_module.name}.{nss_module.value}']
    return mod_ptr[nss_op.value]
