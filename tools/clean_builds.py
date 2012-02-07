#!/usr/bin/env python3.2
"""
Simple script for pruning old builds.

Garrett Cooper, February 2012
"""

import argparse
import os
import sys
import time


# Seconds in a day.
DAY = 24 * 3600


def rm_old_dirs(rootdir, expire_time=(30 * DAY)):
    """Nuke everything under '''rootdir''' older than '''expire_time'''.
    """

    os.chdir(rootdir)

    expiration_date = time.time() - expire_time

    for dirname in \
        filter(lambda e: os.path.isdir(e) and os.stat(e).st_ctime < expiration_date,
               os.listdir('.')):
        print('Removing %s' % (dirname, ))
        for root, dirs, files, in os.walk(dirname, topdown=False):
            for f in files:
                os.unlink(os.path.join(root, f))
        os.rmdir(dirname)


def main(argv):
    """main"""

    parser = argparse.ArgumentParser()

    parser.add_argument('-e', '--expire-date',
                        type=int,
                        default=30,
                        help='number of days before builds expire',
                        )

    args, dirs = parser.parse_known_args()
    if not dirs:
        parser.error('you must specify one or more directories')

    for buildroot in dirs:
        rm_old_dirs(buildroot, expire_time=(args.expire_date * DAY))

if __name__ == '__main__':
    main(sys.argv[1:])
