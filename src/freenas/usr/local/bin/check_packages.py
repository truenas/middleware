#!/usr/local/bin/python -R

import os
import sys
import getopt
import stat

sys.path.append("/usr/local/lib")

import freenasOS.Package as Package

def usage():
    print >> sys.stderr, "Usage: %s [-R root]" % sys.argv[0]
    sys.exit(1)

def main():
    root = ""
    try:
        opts, args = getopt.getopt(sys.argv[1:], "R:")
    except getopt.GetOptError as err:
        print >> sys.stderr, str(err)
        usage()

    for (o, a) in opts:
        if o == "-R":
            root = a
        else:
            usage()

    pkgdb = Package.PackageDB(root)

    files = pkgdb.FindFilesForPackage()
    # That gets us all the files!  Easy enough
    # Now we iterate them, and compare them against the actual filesystem
    for object in files:
        full_path = root + object["path"]
        try:
            st = os.lstat(full_path)
        except OSError as e:
            print >> sys.stderr, "Entry %s does not exist in filesystem" % object["path"]
        else:
            # Now we check the type, mode, flags, owner, and group
            if object["kind"] == "dir" and stat.S_ISDIR(st.st_mode) == 0:
                print >> sys.stderr, "Entry %s is listed as a directory but is not" % object["path"]
            elif object["kind"] == "file" and stat.S_ISREG(st.st_mode) == 0:
                print >> sys.stderr, "Entry %s is listed as a regular file but is not" % object["path"]
            elif object["kind"] == "slink" and stat.S_ISLNK(st.st_mode) == 0:
                print >> sys.stderr, "Entry %s is listed as a symbolic link but is not" % object["path"]
            if object["uid"] != st.st_uid:
                print >> sys.stderr, "Entry %s is listed as owned by uid %d but has uid %d" % (object["path"], object["uid"], st.st_uid)
            if object["gid"] != st.st_gid:
                print >> sys.stderr, "Entry %s is listed with gid %d but has gid %d" % (object["path"], object["gid"], st.st_gid)
            if object["flags"] != st.st_flags:
                print >> sys.stderr, "Entry %s is listed with flags %#x but has flags %#x" % (object["path"], object["flags"], st.st_flags)
            if object["mode"] != stat.S_IMODE(st.st_mode):
                print >> sys.stderr, "Entry %s is listed with mode %#o but has mode %#o" % (object["path"], object["mode"], stat.S_IMODE(st.st_mode))


if __name__ == "__main__":
    main()
    sys.exit(0)

