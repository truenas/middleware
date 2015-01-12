#!/usr/local/bin/python
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
    print >> sys.stderr, "Usage: %s -M manifest [-P package_dir] root" % sys.argv[0]
    print >> sys.stderr, "\tNote:  package dir is parent of Packages directory"
    sys.exit(1)

if __name__ == "__main__":
    mani_file = None
    package_dir = None
    try:
        opts, args = getopt.getopt(sys.argv[1:], "M:P:")
    except getopt.GetoptError as err:
        print >> sys.stderr, str(err)
        usage()

    for (o, a) in opts:
        if o == "-M": mani_file = a
        elif o == "-P": package_dir = a
        else: usage()

    if len(args) != 1:
        usage()

    root = args[0]

    config = Configuration.Configuration()
    if package_dir is not None:
        config.SetPackageDir(package_dir)

    if mani_file is None:
        manifest = config.SystemManifest()
    else:
        # We ignore the signature because freenas-install is
        # called from the ISO install, and the GUI install, which
        # have their own checksums elsewhere.
        manifest = Manifest.Manifest(config, require_signature = False)
        manifest.LoadPath(mani_file)

    installer = Installer.Installer(manifest = manifest, root = root, config = config)

    if installer.GetPackages() != True:
        print >> sys.stderr, "Huh, could not install and yet it returned"

    installer.InstallPackages(PrintProgress)
    manifest.Save(root)
    sys.exit(0)
