from .services.activedirectory import ADDirectoryService
from .services.ipa import IpaDirectoryService
from .services.ldap import LdapDirectoryService


all_directory_services = [
    ADDirectoryService,
    IpaDirectoryService,
    LdapDirectoryService
]


class DirectoryServices:

    __slots__ = (
        '_activedirectory',
        '_ipa',
        '_ldap',
        '_fields'
    )

    def __init__(self):
        self._fields = tuple(
            x.lstrip('_') for x in self.__slots__ if x != '_fields'
        )
        self._activedirectory = None
        self._ipa = None
        self._ldap = None

    @property
    def activedirectory(self):
        return self._activedirectory

    @activedirectory.setter
    def activedirectory(self, ds):
        if not isinstance(ds, ADDirectoryService):
            raise TypeError(f'{type(ds)}: not ADDirectoryService type')

        self._activedirectory = ds

    @property
    def ipa(self):
        return self._ipa

    @ipa.setter
    def ipa(self, ds):
        if not isinstance(ds, IpaDirectoryService):
            raise TypeError(f'{type(ds)}: not IpaDirectoryService type')

        self._ipa = ds

    @property
    def ldap(self):
        return self._ldap

    @ldap.setter
    def ldap(self, ds):
        if not isinstance(ds, LdapDirectoryService):
            raise TypeError(f'{type(ds)}: not LdapDirectoryService type')

        self._ldap = ds


registered_services_obj = DirectoryServices()


def get_enabled_ds():
    for entry in registered_services_obj._fields:
        if (ds := getattr(registered_services_obj, entry)) is None:
            continue

        if ds.is_enabled():
            return ds

    return None
