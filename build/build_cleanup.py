#!/usr/bin/env python

import argparse, os, sys, time

def error_and_exit(cmd, starting_path):
    print "Failed: %s" % cmd
    print os.getcwd()
    os.chdir(starting_path)
    sys.exit(1)

def main(starting_path):
    """Clean up a build environment.  Inspired by a shell
       script of the same name.
    """

    curpath = os.getcwd()

    mount = os.popen("mount | grep %s | grep os-base" % curpath).readlines()
    for dir in mount:
        os.system("umount -f %s" % dir.split(" ")[2])

    if os.path.exists("os-base"):
        cmd = "chflags -R noschg os-base"
        ret = os.system(cmd)
        if ret:
            error_and_exit(cmd, starting_path)
        cmd = "rm -rf os-base"
        ret = os.system(cmd)
        if ret:
            error_and_exit(starting_path)

    os.chdir(starting_path)

if __name__ == "__main__":
    starting_path = os.getcwd()
    os.chdir(os.path.dirname(os.path.realpath(__file__)))
    os.chdir("..")
    parser = argparse.ArgumentParser(description='Cleanup a build environment.')
    parser.add_argument('-n', action='store_true',
                        help="Print out the path to be cleaned up and exit")
    args = parser.parse_args()
    if args.n:
        print "\nDirectory to clean: %s" % os.getcwd()
        sys.exit()
    main(starting_path)
    os.chdir(starting_path)
