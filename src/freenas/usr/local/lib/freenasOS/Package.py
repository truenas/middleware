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
        self.SetName(name)
        self.SetVersion(version)
        self.SetChecksum(checksum)
        return

    def dict(self):
        rv = {}
        rv[NAME_KEY] = self.Name()
        rv[VERSION_KEY] = self.Version()
        rv[CHECKSUM_KEY] = self.Checksum()
        if self._updates is not None and len(self._updates) > 0:
            rv[UPGRADES_KEY] = self._updates
        if self._size is not None:
            rv[SIZE_KEY] = self._size
        return rv

    def MarkDirty(self, b = True):
        self._dirty = b
        return

    def Size(self):
        return self._size

    def SetSize(self, size):
        self._size = size
        self.MarkDirty()

    def Name(self):
        return self._name

    def SetName(self, name):
        self._name = name
        self.MarkDirty()
        return

    def Version(self):
        return self._version

    def SetVersion(self, version):
        self._version = version
        self.MarkDirty()
        return

    def Checksum(self):
        return self._checksum

    def SetChecksum(self, checksum):
        self._checksum = checksum
        self.MarkDirty()
        return

    def AddUpdate(self, old, checksum, size = None):
        if self._updates == None: self._updates = []
        t = { VERSION_KEY : old, CHECKSUM_KEY : checksum }
        if size is not None: t[SIZE_KEY] = size
        self._updates.append(t)

        return

    def Updates(self):
        if self._updates is None: return []
        return self._updates

    def FileName(self, old = None):
        # Very simple function, simply concatenate name, version.
        # Format is <name>-<version>.tgz, or
        # <name>-<old>-<version>.tgz if old is not None.
        if old is None:
            return "%s-%s.tgz" % (self.Name(), self.Version())
        else:
            return "%s-%s-%s.tgz" % (self.Name(), old, self.Version())
