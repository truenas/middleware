#!/usr/local/bin/python -R

import os
import sys
import getopt

sys.path.append("/usr/local/lib")

import freenasOS.Manifest as Manifest
import freenasOS.Configuration as Configuration
import freenasOS.Package as Installer

debug = 0
quiet = False
verbose = 0

def usage():
    print >> sys.stderr, "Usage: %s [-R root] [-M manifest_file] <cmd>, where cmd is one of:" % sys.argv[0]
    print >> sys.stderr, "\tcheck\tCheck for updates"
    print >> sys.stderr, "\tupdate\tDo an update"
    print >> sys.stderr, "\tinstall\tInstall"
    sys.exit(1)

def CheckForUpdates(root = None):
    """
    Check for an updated manifest.
    Very simple, uses the configuration module.
    Returns the new manifest if there is an update,
    and None otherwise.
    """
    conf = Configuration.Configuration()
    cur = Configuration.SystemManifest(root)
    m = conf.FindNewerManifest(cur.Sequence())
    if verbose > 1 or debug > 0:
        print >> sys.stderr, "Current sequence = %d, available sequence = %d" % (cur.Sequence(), m.Sequence() if m is not None else 0)
    return m

def Update(root = None):
    """
    Perform an update.  Calls CheckForUpdates() first, to see if
    there are any. If there are, then magic happens.
    """
    new_man = CheckForUpdates(root)
    if new_man is None:
        return
    print "I MUST UPDATE OR MY HEAD WILL EXPLODE"
    return

def Install(root = None, manifest = None):
    """
    Perform an install.  Uses the system manifest, and installs
    into root.  root must be set.
    """
    if root is None:
        print >> sys.stderr, "Install must have target root specified"
        usage()
    conf = Configuration.Configuration()
    if manifest is not None:
        cur = Manifest.Manifest()
        try:
            cur.LoadPath(manifest)
        except Exception as e:
            print >> sys.stderr, "Could not load manifest from %s: %s" % (manifest, str(e))
            return False
    else:
        try:
            cur = Configuration.SystemManifest()
        except:
            print >> sys.stderr, "Cannot get system manifest"
            return False
    if cur is None or cur.Packages() is None:
        raise Exception("Cannot load configuration")

    print "Want to install into %s" % root
    #
    # To install, we have to grab each package in the manifest,
    # and install them into the specified root directory.
    # When we are done, we write out the system manifest into
    # the manifest directory.
    for pkg in cur.Packages():
        print "Package %s" % pkg.Name()
        filename = Manifest.FormatName(pkg.Name(), pkg.Version())
        f = conf.FindPackage(filename, pkg.Checksum())
        if f is None:
            print >> sys.stderr, "\tCould not find package file for %s" % filename
            return False
        else:
            if Installer.install_file(f, root) == False:
                print >> sys.stderr, "Could not install package %s" % filename
                return False
            else:
                print "%s installed" % pkg.Name()
    conf.StoreManifest(cur, root)

    return True

try:
    opts, args = getopt.getopt(sys.argv[1:], "qvdR:M:")
except getopt.GetoptError as err:
    print str(err)
    usage()

root = None
manifile = None

for o, a in opts:
    if o == "-v":
        verbose += 1
    elif o == "-q":
        quiet = True
    elif o == "-d":
        debug += 1
    elif o == "-R":
        root = a
    elif o == "-M":
        manifile = a
    else:
        assert False, "unhandled option"

if root is not None and os.path.isdir(root) == False:
    print >> sys.stderr, "Specified root (%s) does not exist" % root
    sys.exit(1)

if len(args) != 1:
    usage()

if args[0] == "check":
    r = False if CheckForUpdates(root) is None else True
    
    if verbose > 0 or debug > 0:
        print >> sys.stderr, "Newer manifest found" if r else "No newer manifest found"
    if r:
        sys.exit(0)
    else:
        sys.exit(1)
elif args[0] == "update":
    Update(root)
elif args[0] == "install":
    if Install(root, manifile) == False:
        print >> sys.stderr, "Could not install into %s" % root
        sys.exit(1)
else:
    usage()

