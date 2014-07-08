#!/usr/bin/python -R

import os
import sys
import ConfigParser
import tempfile
import subprocess
import hashlib

import urllib2

sys.path.append("/usr/local/lib")

import freenasOS.ixExceptions
import freenasOS.Manifest

_config_file = "/usr/local/etc/freenas.conf"
_local_config_file = "/usr/local/etc/freenas-local.conf"
_manifest_file = "/etc/manifest"

"""
Class and methods for FreeNAS installation configuration
information.

The configuration file specifies what the search paths are,
and what trains are supported.

There are two configuration files:  config_file is
read first, then local_config_file (if it exists).
Search locations from local are done first.

"""

_globalconfiguration = None

def Configuration():
    global _globalconfiguration
    if _globalconfiguration is None:
        _globalconfiguration = ixConfiguration()
    return _globalconfiguration

#
# Try getting a local file, with a set of suffixes.
# If the file exists, return the first one.
def TryFileSuffixes(path, suffixes):
    for s in suffixes:
        t = "%s.%s" % (path, s)
        if os.path.isfile(t): return open(t, "r")
    return None

def TryURLSuffixes(path, suffixes):
    for s in suffixes:
        t = "%s.%s" % (path, s)
        print >> sys.stderr, "Trying URL %s" % t
        rv = FetchFile(t)
        if rv is not None: return rv
    return None

# Get a URL, returning a patch to a temporary file.
# Returns None if the file can't be found.  It is
# up to the caller to clean up the file.
# This is just a wrapper for fetch; using the
# various modules provided by python may be better,
# but is more complicated.
def FetchFile(url):
    return FetchFileURL(url)
    (dc, t) = tempfile.mkstemp()
    args = ["/usr/bin/fetch", "-o", t, url]
    print "args = %s" % args
    r = subprocess.call(args)

    if r != 0:
        os.remove(t)
        t = None

    return t

# Using urllib2
# As a note, urllib2 doesn't check https certificate integrity.
# This may be a problem
def FetchFileURL(url):
    try:
        print >> sys.stderr, "FetchFileURL(%s)" % url
        retval = tempfile.NamedTemporaryFile(prefix="sef-freenas")
        req = urllib2.Request(url)
        req.add_header("X-FreeNAS-Manifest", "1")
        furl = urllib2.urlopen(req)
        retval.write(furl.read())
        retval.seek(0)
        return retval
    except:
        return None


def SystemManifest(root = None):
    m = freenasOS.Manifest.ixManifest()
    if root is None:
        prefix = ""
    else:
        prefix = root + "/"
    m.load_path(prefix + _manifest_file)
        
    return m

class ixConfiguration(object):
    MANIFEST_NAME = "LATEST"
    MANIFEST_PATH = "%s/%s/LATEST"
    PACKAGE_PATH = "%s/Packages/%s"

    config_file = "/usr/local/etc/freenas.conf"
    manifest_file = "/etc/manifest"
    local_config_file = "/usr/local/etc/freenas-local.conf"
    __trains = {}
    __search = []
    __current_train = None

    def __init__(self):
        try:
            cfParser = ConfigParser.ConfigParser()
            with open(_local_config_file, "r") as f:
                cfParser.readfp(f)
                # Right now, we only look for a "search" section.
                # There, we add search locations as they show up.
                sp = cfParser.items("Search")
                print >> sys.stderr, "sp = %s" % (sp)
                for (name, locs) in sp:
                    spa = locs.split()
                    for L in spa:
                        if L == "\\":
                            continue
                        else:
                            self.__search.append(L)
        except:
            print "First exception, %s" % sys.exc_info()[0]
            pass
        try:
            cfParser = ConfigParser.ConfigParser()
            with open(_config_file, "r") as f:
                cfParser.readfp(f)
                for section in cfParser.sections():
                    if section == "Defaults":
                        sp = cfParser.get(section, "search")
                        if sp is not None:
                            spa = sp.split()
                            # Handle backslash for line continuation
                            for L in spa:
                                if L == "\\":
                                    continue
                                self.__search.append(L)
                        self.__current_train = cfParser.get(section, "train")
                    else:
                        # A train section
                        # We only care about two values right now, current and last
                        tmp = {}
                        tmp["current"] = cfParser.get(section, "current")
                        tmp["last"] = cfParser.get(section, "last")
                        self.__trains[section] = tmp
        except:
            print "Exception %s" % sys.exc_info()[0]
            pass
        print "search = %s" % self.__search
        print "trains = %s" % self.__trains
        print "current = %s" % self.__current_train
        if self.__trains is None:
            raise ixManifestTrainError("Current train is not defined")
        return

    def AddSearch(self, s):
        self.__search.insert(0, s)

    def FindNewerManifest(self, sequence, Train = None):
        """
        Go through the search path looking for a newer
        manifest file than sequence.  Return None if one
        isn't found.
        This looks for MANIFEST_NAME at each of the search paths,
        using MANIFEST_PATH to construct it.
        """
        if Train is None:
            Train = self.__current_train
        for loc in self.__search:
            full_path = ixConfiguration.MANIFEST_PATH % (loc, Train)
            print full_path
            tf = FetchFile(full_path)
            if tf is not None:
                print "%s -> %s" % (full_path, tf.name)
                candidate = Manifest.ixManifest()
                candidate.load_file(tf)
                if candidate.Sequence() > sequence:
                    return candidate
        return None

    def FindManifest(self, Train = None):
        """
        Look for the latest manifest file for the given train.
        Convenience function for FindNewerManifest
        """
        return self.FindNewerManifest(0, Train)

    def StoreManifest(self, m, root = None):
        """
        Write the current manifest into the system manifest
        """
        m.store("%s/%s" % ("" if root is None else root, _manifest_file))

    def FindPackage(self, pkgname, checksum = None):
        """
        Look for the package named, via the normal search mechanisms.
        pkgname must be the name of the package including version,
        e.g. base_os-1.0.  (The function will try various suffixes,
        including none, .tgz, txz, and .tar.bz2.)  If checksum is
        set, then when it finds a file, it will attempt to verify
        the checksum; if the checksum doesn't match, it'll go on
        to the next candidate.  If a match is found, it will return
        a file-like object; otherwise, it returns None
        """
        suffixes = [ "tgz", "tar", "txz", "tbz", "" ]
        for base in self.__search:
            temppath = "%s/Packages/%s" % (base, pkgname)
            print >> sys.stderr, "^^^^ temppath = %s" % temppath
            full_path = None
            if base.startswith("/"):
                fobj = TryFileSuffixes(temppath, suffixes)
            else:
                fobj = TryURLSuffixes(temppath, suffixes)
            if fobj is not None:
                if checksum is None:
                    return fobj
                else:
                    temp_checksum = hashlib.sha256(fobj.read()).hexdigest()
                    if temp_checksum == checksum:
                        fobj.seek(0)
                        return fobj
                    else:
                        print >> sys.stderr, "pkg %s:  temp_checksum = %s, checksum = %s, not a match" % (pkgname, temp_checksum, checksum)
            else:
                print >> sys.stderr, "fobj for %s is None" % temppath
        return None

if __name__ == "__main__":
    cf = ixConfiguration()

    man = cf.FindManifest()
    if man is not None:
        print "manifest = %s" % man.dict()
        print "Sequence %d" % man.Sequence()
        for pkg in man.Packages():
            print "Package %s, version %s" % (pkg.Name(), pkg.Version())

    else:
        print >> sys.stderr, "Huh, no manifest file"


    man = cf.FindNewerManifest(102)
    if man is None:
        print "No newer manifest"
    else:
        print "newer manifest = %s" % man.dict()
