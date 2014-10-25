#!/usr/local/bin/python -R

"""
Utility to manage a manifest file.

Usage is:  manifest_util [-C conf] [-M manifest] [-R path] cmd [args]
-C specifies a configuration file to use (defaults to system config file)
-M specifies a manifest file (defaults to system manifest)
-R specifies a remote manifest name by train/sequence.  E.g., FreeNAS-EXPERIMENTAL/LATEST
Commands are:

list	List the package contents of the manifest
sign	Sign the manifest.
train	Print out the train name
sequence	Print out the sequence number
version	Print out the verison name (if any)
notes	Print out the release notes (if any)
show	Print out the sequence number, train name, and version number
"""

import os, sys, getopt
import logging, logging.config

logging.config.dictConfig({
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'simple': {
            'format': '[%(name)s:%(lineno)s] %(message)s',
        },
    },
    'handlers': {
        'std': {
            'class': 'logging.StreamHandler',
            'level': 'DEBUG',
            'stream': 'ext://sys.stdout',
        },
    },
    'loggers': {
        '': {
            'handlers': ['std'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
})
log = logging.getLogger("manifest_util")

sys.path.append("/usr/local/lib")

import freenasOS.Manifest as Manifest
import freenasOS.Configuration as Configuration
from freenasOS.Configuration import ChecksumFile
import freenasOS.Package as Package

def usage(subopt = None):
    print >> sys.stderr, "Usage: %s [-M manifest] [-C config] [-R remote] cmd [args]"
    print >> sys.stderr, "cmd is one of:\n"
    print >> sys.stderr, "\tlist\tList the package contents of the manifest"
    print >> sys.stderr, "\tsign key\tSign the manifest with the given key file"
    print >> sys.stderr, "\ttrain\tPrint the train name"
    print >> sys.stderr, "\tsequence\tPrint the sequence number"
    print >> sys.stderr, "\tversion\tPrint the version name (if any)"
    print >> sys.stderr, "\tnotes\tPrint out the release notes (if any)"
    print >> sys.stderr, "\tshow\tPrint out the sequence number, train name, and version number"

    if subopt is not None:
        print >> sys.stderr, "\n%s" % subopt

    sys.exit(1)

def show_cmd(mani, args):
    """
    Print out the sequence number, train name, and version number.  Optional arguments are:
    -q	Only print out the values, one per line; do not include package upgrades.
    -s	Print out values in shell-format, a la stat(1).
    """
    quiet = False
    shell = False

    def show_usage():
        usage("show [-q] [-s]:\n\t-q\tOnly print the values; do not include package upgrades;\n"
              "\t-s\tPrint out values in shell-format, a la stat(1)")

    try:
        opts, args = getopt.getopt(args, "qs")
    except getopt.GetoptError as err:
        print str(err)
        show_usage()

    for o, a in opts:
        if o == '-q':
            quiet = True
        elif o == '-s':
            shell = True
        else:
            show_usage()

    def PrintValue(name, val, indent = ""):
        if val is None:
            return
        if shell:
            try:
                int(val)
            except:
                s = "%s=\"%s\"" % (name, val)
            else:
                s = "%s=%s" % (name, val)
        elif quiet:
            s = val
        else:
            s = "%s%s:\t%s" % (indent, name, val)
        print s

    PrintValue("Version", mani.Version())
    PrintValue("Sequence", mani.Sequence())
    PrintValue("Train", mani.Train())
    if shell:
        for pkg in mani.Packages():
            updates = []
            for upd in pkg.Updates():
                updates.append(upd[Package.VERSION_KEY])
            if len(updates) == 0:
                x = ""
            else:
                x = ":" + ",".join(updates)
            print "Package[\"%s\"]=\"%s%s\"" % (pkg.Name(), pkg.Version(), x)
    else:
        list_cmd(mani, ["-q"] if quiet else None)
    return

def list_cmd(mani, args):
    """
    Print out the package contents of the manifest file.  Optional arguments are:
    -q	Only print the name and version of the packages, do not include upgrades.
    """
    quiet = False

    def list_uasge():
        usage("list [-q]:\n\t-q\tOnly print the name and version of the packages")

    try:
        opts, args = getopt.getopt(args, "q")
    except getopt.GetoptError as err:
        print str(err)
        list_usage()

    for o, a in opts:
        if o == "-q":
            quiet = True
        else:
            list_usage()

    for pkg in mani.Packages():
        if quiet:
            print "%s-%s" % (pkg.Name(), pkg.Version())
        else:
            print "Package %s:" % pkg.Name()
            print "\tVersion %s" % pkg.Version()
            if pkg.Size() is not None:
                print "\tSize %d" % pkg.Size()
            print "\tChecksum %s" % pkg.Checksum()
            for upd in pkg.Updates():
                print "\t\tUpdate from %s: checksum %s" % (upd[Package.VERSION_KEY], upd[Package.CHECKSUM_KEY])
    return

def sign_manifest(mani, path, a):
    key_file = None
    output_file = sys.stdout
    overwrite = False
    output_path = None

    try:
        opts, args = getopt.getopt(a, "WO:")
    except getopt.GetoptError as err:
        print str(err)
        print >> sys.stderr, "sign [-W | -O <file>] key"
        usage()

    for o, a in opts:
        if o == '-W':
            overwrite = True
        elif o == 'O':
            output_path = a
        else:
            print >> sys.stderr, "sign [-W | -O <file>] key"
            usage()

    if len(args) == 0:
        print >> sys.stderr, "Signing requires a key file"
        usage()

    if output_path and overwrite:
        print >> sys.stderr, "sign [-W | -O <file>] key"
        usage()

    if overwrite:
        output_file = open(path, "w+")
    if output_path:
        output_file = open(output_path, "wx")

    key_file = args[0]
    key_data = open(key_file).read()
    mani.SignWithKey(key_data)
    mani.StoreFile(output_file)

    return

def main():
    config_file = None
    mani_file = None
    remote_train = None

    try:
        opts, args = getopt.getopt(sys.argv[1:], "C:M:R:")
    except getopt.GetoptError as err:
        print str(err)
        usage()

    for o, a in opts:
        if o == "-C":
            config = a
        elif o == "-M":
            mani_file = a
        elif o == "-R":
            if "/" in a:
                (remote_train, remote_manifest) = a.split("/")
                if remote_manifest is not None and remote_manifest.startswith("FreeNAS-"):
                    remote_manifest = remote_manifest[len("FreeNAS-"):]
        else:
            usage()

    if len(args) == 0:
        usage()

    conf = Configuration.Configuration(file = config_file)
    if remote_train is not None:
        mani = conf.GetManifest(remote_train, remote_manifest)
    elif mani_file is not None:
        mani = Manifest.Manifest(conf)
        mani.LoadPath(mani_file)
    else:
        mani = conf.SystemManifest()

    if mani is None:
        print >> sys.stderr, "Unable to load manifest"
        return(1)


    if args[0] == "list":
        list_cmd(mani, args[1:])
    elif args[0] == "train":
        print mani.Train()
    elif args[0] == "sequence":
        print mani.Sequence()
    elif args[0] == "version":
        if mani.Version() is not None:
            print mani.Version()
    elif args[0] == "notes":
        if mani.Notes() is not None:
            print mani.Notes()
    elif args[0] == "show":
        show_cmd(mani, args[1:])
    elif args[0] == "sign":
        sign_manifest(mani, mani_file, args[1:])
    else:
        usage()

    return 0

if __name__ == "__main__":
    sys.exit(main())

