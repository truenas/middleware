#!/usr/bin/env python

import os, signal, sys, time

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

    if os.path.isdir("pbi"):
        # TODO: Perhaps there's a more elegent way to get a zfs
        # dataset from a path.
        zfs = False
        zfs_list = os.popen("zfs get -H mountpoint").readlines()
        for line in zfs_list:
            try:
                path = line.split("\t")[0]
                dataset = line.split("\t")[2]
            except IndexError:
                continue

                if path == os.path.realpath("pbi"):
                    zfs = True
                    try:
                        os.system("zfs destroy -r %s" % dataset)
                    except OSError as err:
                        os.chdir(starting_path)
                        sys.exit("Cleanup failed", err)

        if not zfs or os.path.isdir("pbi"):
            try:
                os.system("rm -rf pbi")
            except OSError as err:
                os.chdir(starting_path)
                sys.exit("Cleanup failed", err)

    os.chdir(starting_path)

if __name__ == "__main__":
    # I'm not sure about this directory detection logic,
    # so print out the directory we are going to use
    # and give the user a chance to bail out before
    # we start doing destructive things.
    starting_path = os.getcwd()
    os.chdir(os.path.dirname(sys.argv[0]))
    os.chdir("..")
    print "\nOperating in directory %s" % os.getcwd()

    def handler(signum, frame):
        print "\nHere we go"
        time.sleep(1)
        main(starting_path)

    signal.signal(signal.SIGALRM, handler)
    signal.alarm(7)
    raw_input("Press enter in 7 seconds to abort")
    os.chdir(starting_path)
    sys.exit()
