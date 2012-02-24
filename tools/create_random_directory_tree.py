#!/usr/bin/env python
"""
A module for creating a random directory tree.

Beware... this uses recursion.. and will eat up memory quickly if you go too many levels deep
(and will die of MemoryError's if you exceed sys.getrecursionlimit()).

XXX: This only works with directories and regular files for now.
XXX: This is hacky and could be improved.
XXX: pjdfstest is another potentially useful item to try instead of this script
     (but it doesn't exist on 8.2 and it would require hacking nanobsd to get
     to work which I'm trying to avoid).

Usage:
    python create_random_directory_tree.py \
        [max-number-of-files [max-number-of-directories [nested-levels]]]

Garrett Cooper, December 2011
"""

import os
import random
import subprocess
import sys
import tempfile
import threading

ONE_MB = 1024 * 1024
DIE_SIZE = 512 * ONE_MB
CHUNKSIZE = 10 * ONE_MB
NCPUS = int(subprocess.check_output(['sysctl', '-n', 'kern.smp.cpus']).strip())

# XXX: move to argparser logic in main(..).
try:
    MAX_NUMBER_FILES = int(sys.argv[1])
except (IndexError, ValueError):
    MAX_NUMBER_FILES = random.choice(xrange(1, 250))

try:
    MAX_NUMBER_DIRECTORIES = int(sys.argv[2])
except (IndexError, ValueError):
    MAX_NUMBER_DIRECTORIES = random.choice(xrange(1, 10))

try:
    NESTED_LEVELS = int(sys.argv[3])
except (IndexError, ValueError):
    NESTED_LEVELS = 0

def create_nested_dirs(root, level):
    """Create a nested directory tree with a random number of subdirectories.

    Returns a list of directories, or if level is 0, just a single element list
    with the root directory passed in.
    """

    if not level:
        return [root]
    _directories = [tempfile.mkdtemp(dir=root) for i in
                    xrange(random.choice(xrange(1, MAX_NUMBER_DIRECTORIES)))]
    directories = []
    for directory in _directories:
        directories.extend(create_nested_dirs(directory, level-1))
    return directories

def spam_dir(directory):
    """Spam directory with {1..MAX_NUMBER_FILES} temporary randomly generated files.
    """
    with open('/dev/urandom', 'rb') as urandom_fd:
        for i in xrange(random.choice(xrange(1, MAX_NUMBER_FILES))):
            tmpfile = tempfile.mktemp(dir=directory)
            filesize = random.choice(xrange(DIE_SIZE))
            with open(tmpfile, 'wb') as tmpfd:
                for j in xrange(filesize / CHUNKSIZE):
                    tmpfd.write(urandom_fd.read(CHUNKSIZE))
                leftover_filesize = filesize % CHUNKSIZE
                if leftover_filesize:
                    tmpfd.write(urandom_fd.read(leftover_filesize))

def main(argv):
    """Main"""

    directories = create_nested_dirs(os.getcwd(), NESTED_LEVELS)
    lock = threading.Lock()

    def spam_dir_mt(lock):
        """Spamming directory pool -- multithreaded style."""
        while True:
            lock.acquire()
            if directories:
                directory = directories.pop()
                lock.release()
                spam_dir(directory)
            else:
                lock.release()
                break
        print '[Thread %d]: done' % (threading.currentThread().ident, )

    threads = []
    for cpu in xrange(NCPUS):
        threads.append(threading.Thread(target=spam_dir_mt, args=(lock, )))
        threads[-1].start()
        print '[Thread %d]: started' % (threads[-1].ident, )

    for thread in threads:
        thread.join()

if __name__ == '__main__':
    main(sys.argv)
