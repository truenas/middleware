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


    def __init__(self, *args):
        self._dict = {}
        # We can be called with a dictionary, or with (name, version, checksum)
        if len(args) == 1 and isinstance(args[0], dict):
            tdict = args[0]
            for k in tdict.keys():
                if k == UPGRADES_KEY:
                    updates = []
                    for update in tdict[UPGRADES_KEY]:
                        updates.append(update.copy())
                    self._dict[UPGRADES_KEY] = updates
                else:
                    self._dict[k] = tdict[k]
        else:
            if len(args) > 0: self.SetName(args[0])
            if len(args) > 1: self.SetVersion(args[1])
            if len(args) > 2: self.SetChecksum(args[2])
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
