#!/usr/local/bin/python
import sys
import traceback

sys.path.append("/usr/local/lib")
from freenasOS import Configuration

if __name__ == '__main__':
    try:
        error_flag, ed, warn_flag, wl = Configuration.do_verify()
    except IOError, e:
        traceback.print_exc()
        sys.exit(74)

    if error_flag or warn_flag:
        print "The following inconsistencies were found in your current install:"

        if ed['checksum']:
            print "\nList of Checksum Mismatches:\n"
            for entry in ed['checksum']:
                print entry["path"]

        if ed['notfound']:
            print "\nList of Files/Directories/Symlinks not Found:\n"
            for entry in ed['notfound']:
                print entry["path"]

        if ed['wrongtype']:
            print "\nList of Incorrect Filetypes:\n"
            for entry in ed['wrongtype']:
                print entry["path"], "\t" , entry["problem"]

        if wl:
            print "\nList of Permission Errors:\n"
            for entry in wl:
                print entry["path"], "\t" , entry["problem"].replace("\n",' ')
        sys.exit(1)

    else:
        print "All Files, Directories and Symlinks in the system were verified successfully"
        sys.exit(0)