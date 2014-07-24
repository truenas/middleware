#!/usr/local/bin/python -R
import os
import sys

import getopt

sys.path.append("/usr/local/lib")

import freenasOS.Manifest as Manifest
import freenasOS.Package as Package
import freenasOS.Configuration as Configuration
import freenasOS.Installer as Installer

def PrintProgress(pct, name):
    print >> sys.stderr, "Got %s (%.2f%%)" % (name, pct)

def usage():
    print >> sys.stderr, "Usage: %s -M manifest [-C config] root" % sys.argv[0]
    sys.exit(1)

if __name__ == "__main__":
    mani_file = None
    config_file = None
    try:
        opts, args = getopt.getopt(sys.argv[1:], "M:C:")
    except getopt.GetoptError as err:
        print >> sys.stderr, str(err)
        usage()

    for (o, a) in opts:
        if o == "-M": mani_file = a
        elif o == "-C": conf_file = a
        else: usage()

    if len(args) != 1:
        usage()

    root = args[0]

    config = Configuration.Configuration(file = conf_file)
    print "config search locations = %s" % config.SearchLocations()
    if mani_file is None:
        manifest = config.SystemManifest()
    else:
        manifest = Manifest.Manifest(config)
        manifest.LoadPath(mani_file)
        manifest.Validate()

    installer = Installer.Installer(manifest = manifest, root = root, config = config)

    if installer.GetPackages() != True:
        print >> sys.stderr, "Huh, could not install and yet it returned"

    installer.InstallPackages(PrintProgress)
    manifest.StorePath(root + "/etc/manifest")
