#!/usr/local/bin/python -R

import os, sys, getopt

sys.path.append("/usr/local/lib")

import freenasOS.Manifest as Manifest
import freenasOS.Configuration as Configuration
import freenasOS.Package as Installer

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
    conf = Configuration.Configuration(root)
    cur = conf.SystemManifest()
#    m = conf.FindNewerManifest(cur.Sequence())
    m = conf.FindLatestManifest()
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

    print >> sys.stderr, "Newer manifest found" if r else "No newer manifest found"
    if r:   
        sys.exit(0)
    else:
        sys.exit(1)
elif args[0] == "update":
    Update(root)

else:
    usage()
