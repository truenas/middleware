import os
import sys

import Exceptions


NAME_KEY = "Name"
VERSION_KEY = "Version"
CHECKSUM_KEY = "Checksum"
SIZE_KEY = "FileSize"
UPGRADES_KEY = "Upgrades"
REBOOT_KEY = "RequiresReboot"

class Package(object):
    _name = None
    _version = None
    _checksum = None
    _size = None
    _updates = None
    _dirty = False

    class PackageUpdate(object):
        def __init__(self, pkg, dict):
            self._dict = dict
            self._base = pkg

        def BasePackage(self):
            return self._base

        def Version(self):
            return self._dict[VERSION_KEY]

        def Checksum(self):
            if CHECKSUM_KEY in self._dict:
                return self._dict[CHECKSUM_KEY]
            return None
        
        def Size(self):
            if SIZE_KEY in self._dict:
                return self._dict[SIZE_KEY]
            return None

        def SetSize(self, size):
            self._dict[SIZE_KEY] = size

        def RequiresReboot(self):
            if REBOOT_KEY in self._dict:
                return self._dict[REBOOT_KEY]
            else:
                return self._base.RequiresReboot()
            return None

        def SetRequiresReboot(self, rr):
            self._dict[REBOOT_KEY] = bool(rr)
            
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
            if len(args) > 3:  self.SetRequiresReboot(args[3])
            
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

    def AddUpdate(self, old, checksum, size = None, RequiresReboot = None):
        if UPGRADES_KEY not in self._dict:
            self._dict[UPGRADES_KEY] = []
        t = { VERSION_KEY : old, CHECKSUM_KEY : checksum }
        if size is not None: t[SIZE_KEY] = size
        if RequiresReboot is not None:
            if self.RequiresReboot() != RequiresReboot:
                t[REBOOT_KEY] = RequiresReboot
        self._dict[UPGRADES_KEY].append(t)

        return

    def Updates(self):
        if UPGRADES_KEY in self._dict:
            rv = []
            for upd in self._dict[UPGRADES_KEY]:
                rv.append(Package.PackageUpdate(self, upd))
            return rv
        return []

    def Update(self, old_version):
        updates = self.Updates()
        if updates:
            for upd in updates:
                if upd.Version() == old_version:
                    return upd
        return None
    
    def FileName(self, old = None):
        # Very simple function, simply concatenate name, version.
        # Format is <name>-<version>.tgz, or
        # <name>-<old>-<version>.tgz if old is not None.
        if old is None:
            return "%s-%s.tgz" % (self.Name(), self.Version())
        else:
            return "%s-%s-%s.tgz" % (self.Name(), old, self.Version())

    def RequiresReboot(self):
        if REBOOT_KEY in self._dict:
            return self._dict[REBOOT_KEY]
        # If not set, we default to yes, it requires a reboot
        return True

    def SetRequiresReboot(self, val = True):
        self._dict[REBOOT_KEY] = val
        
