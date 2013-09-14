#!/usr/bin/env python

import argparse, os, sys, time

def main(starting_path):
    """Clean up a build environment.  Inspired by a shell
       script of the same name.
    """

    if os.path.exists("os-base"):
        try:
            os.system("chflags -R noschg os-base")
            os.system("rm -rf os-base")
        except OSError as err:
            os.chdir(starting_path)
            sys.exit("Cleanup failed", err)

    # Possibly there are more directories than this that can
    # get left mounted.
    # TODO: Add leftover directories to this list
    for dir in ['os-base/amd64/_.w/dev',
                'os-base/i386/_.w/dev',
                'os-base/amd64/jails/jail-i386/dev']:
        if os.path.isdir(dir):
            os.system("umount %s" % dir)

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
