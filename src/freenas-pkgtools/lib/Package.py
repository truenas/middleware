import os
import sys

import Exceptions

NAME_KEY = "Name"
VERSION_KEY = "Version"
CHECKSUM_KEY = "Checksum"
SIZE_KEY = "FileSize"
UPGRADES_KEY = "Upgrades"

class Package(object):
    _name = None
    _version = None
    _checksum = None
    _size = None
    _updates = None
    _dirty = False


    def __init__(self, name, version, checksum):
        self._dict = {}
        self.SetName(name)
        self.SetVersion(version)
        self.SetChecksum(checksum)
        return

    def dict(self):
        return self._dict

        if self._size is not None:
            rv[SIZE_KEY] = self._size
        return rv

    def Size(self):
        if SIZE_KEY in self._dict:
            return self._dict[SIZE_KEY]
        return None

    def SetSize(self, size):
        self._dict[SIZE_KEY] = size

    def Name(self):
        return self._dict[NAME_KEY]

    def SetName(self, name):
        self._dict[NAME_KEY] = name
        return

    def Version(self):
        return self._dict[VERSION_KEY]

    def SetVersion(self, version):
        self._dict[VERSION_KEY] = version
        return

    def Checksum(self):
        if CHECKSUM_KEY in self._dict:
            return self._dict[CHECKSUM_KEY]
        return None

    def SetChecksum(self, checksum):
        self._dict[CHECKSUM_KEY] = checksum
        return

    def SetUpdates(self, updates):
        self._dict[UPGRADES_KEY] = []
        for upd in updates:
            size = None
            if SIZE_KEY in upd:
                size = up[SIZE_KEY]
            self.AddUpdate(upd[VERSION_KEY], upd[CHECKSUM_KEY], size)
        return

    def AddUpdate(self, old, checksum, size = None):
        if UPGRADES_KEY not in self._dict:
            self._dict[UPGRADES_KEY] = []
        t = { VERSION_KEY : old, CHECKSUM_KEY : checksum }
        if size is not None: t[SIZE_KEY] = size
        self._dict[UPGRADES_KEY].append(t)

        return

    def Updates(self):
        if UPGRADES_KEY in self._dict:
            return self._dict[UPGRADES_KEY]
        return []

    def FileName(self, old = None):
        # Very simple function, simply concatenate name, version.
        # Format is <name>-<version>.tgz, or
        # <name>-<old>-<version>.tgz if old is not None.
        if old is None:
            return "%s-%s.tgz" % (self.Name(), self.Version())
        else:
            return "%s-%s-%s.tgz" % (self.Name(), old, self.Version())
