#!/usr/bin/env python

import argparse
import os
import re
import sys

from subprocess import Popen, PIPE

def parse_index(index_file):
    ports_list = {}
    cmd = "bzip2 -dc " + index_file

    p1 = Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE)
    line=p1.stdout.readline()
    while line != "":
        # Parse a line that looks like:
        # cmake-2.8.12.1|/usr/ports/devel/cmake|/usr/local|Cross-platform Makefile generator|/usr/ports/devel/cmake/pkg-descr|kde@FreeBSD.org|devel||cmake-modules-2.8.12.1_1|http://www.cmake.org/|||
        (portname, port, junk) = line.split('|', 2)
        port = re.sub("/usr/ports/", "", port)
        ports_list[port] = portname 
        line=p1.stdout.readline()

    return ports_list

def parse_ports_txt(ports_file, ports_list):
    ports_to_install = [] 
    f = open(ports_file, "r")
    line = f.readline()
    while line != "":
        line = line.rstrip()
        if ports_list.has_key(line):
            ports_to_install.append(ports_list[line])

        line = f.readline()

    f.close()  

    return ports_to_install

def install_ports(ports_to_install, chroot):
    cmd = "chroot %s /bin/sh -c \"(cd /usr/ports/packages/All ; pkg_add -F " % (chroot)
    for port in ports_to_install:
        cmd = "%s %s.tbz" % (cmd, port)

    cmd = cmd + " )\""
    print cmd
    ret = os.system(cmd)
    if ret != 0:
        sys.exit(ret)

def main(args):
    parser = argparse.ArgumentParser(description='Get list of packages to install')
    parser.add_argument('--ports', help='ports.txt file' )
    parser.add_argument('--index', help='INDEX.bz2 file' )
    parser.add_argument('--chroot', help='jail chroot directory' )
    parser.add_argument('--packages', help='INDEX.bz2 file' )

    args = parser.parse_args()

    ports_list = parse_index(args.index)
    ports_to_install = parse_ports_txt(args.ports, ports_list)
    install_ports(ports_to_install, args.chroot)


if __name__ == "__main__":
    main(sys.argv)
