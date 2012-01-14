#!/usr/local/bin/python
#
# $Id: arcstat.pl,v 389:6a4ad672a88a 2011-08-14 03:40:05Z jhell $
#
# Print out ZFS ARC Statistics exported via kstat(1)
# For a definition of fields, or usage, use arctstat.pl -v  
#
# Author: Neelakanth Nadgir http://blogs.sun.com/realneel
# Comments/Questions/Feedback to neel_sun.com or neel_gnu.org
#
# CDDL HEADER START
#
# The contents of this file are subject to the terms of the
# Common Development and Distribution License, Version 1.0 only
# (the "License").  You may not use this file except in compliance
# with the License.
#
# You can obtain a copy of the license at usr/src/OPENSOLARIS.LICENSE
# or http://www.opensolaris.org/os/licensing.
# See the License for the specific language governing permissions
# and limitations under the License.
#
# When distributing Covered Code, include this CDDL HEADER in each
# file and include the License file at usr/src/OPENSOLARIS.LICENSE.
# If applicable, add the following below this CDDL HEADER, with the
# fields enclosed by brackets "[]" replaced with your own identifying
# information: Portions Copyright [yyyy] [name of copyright owner]
#
# CDDL HEADER END
#
#
# Fields have a fixed width. Every interval, we fill the "v"
# hash with its corresponding value (v[field]=value) using calculate().
# @hdr is the array of fields that needs to be printed, so WE
# JUST iterate over this array and print the values using our pretty printer.

import os
import sys
import time
import getopt 
import re
import copy
import decimal

from decimal import Decimal
from subprocess import Popen, PIPE
from signal import signal, SIGINT

cols = {
    # HDR :   [Size, Description]
    'Time':   [8, "Time"],
    'hits':   [5, "Arc reads per second"],
    'miss':   [5, "Arc misses per second"],
    'read':   [5, "Total Arc accesses per second"],
    'Hit%':   [4, "Arc Hit percentage"],
    'miss%':  [5, "Arc miss percentage"],
    'dhit':   [5, "Demand Data hits per second"],
    'dmis':   [5, "Demand Data misses per second"],
    'dh%':    [3, "Demand Data hit percentage"],
    'dm%':    [3, "Demand Data miss percentage"],
    'phit':   [4, "Prefetch hits per second"],
    'pmis':   [4, "Prefetch misses per second"],
    'ph%':    [3, "Prefetch hits percentage"],
    'pm%':    [3, "Prefetch miss percentage"],
    'mhit':   [5, "Metadata hits per second"],
    'mmis':   [5, "Metadata misses per second"],
    'mread':  [5, "Metadata accesses per second"],
    'mh%':    [3, "Metadata hit percentage"],
    'mm%':    [3, "Metadata miss percentage"],
    'size':   [5, "Arc Size"],
    'tsize':  [5, "Arc Target Size"],
    'mfu':    [5, "MFU List hits per second"],
    'mru':    [5, "MRU List hits per second"],
    'mfug':   [5, "MFU Ghost List hits per second"],
    'mrug':   [5, "MRU Ghost List hits per second"],
    'eskip':  [5, "evict_skip per second"],
    'mtxmis': [6, "mutex_miss per second"],
    'rmis':   [5, "recycle_miss per second"],
    'dread':  [5, "Demand data accesses per second"],
    'pread':  [5, "Prefetch accesses per second"],
}

v = {}
hdr = ['Time', 'read', 'miss', 'miss%', 'dmis', 'dm%',
    'pmis', 'pm%', 'mmis', 'mm%', 'size', 'tsize']
xhdr = ['Time', 'mfu', 'mru', 'mfug', 'mrug', 'eskip',
    'mtxmis', 'rmis', 'dread', 'pread', 'read']
sint = 1       # Print stats every 1 second by default
count = 0      # Print stats forever
hdr_intr = 20  # Print header every 20 lines of output
opfile = None 
sep = '  '     # Default seperator is 2 spaces
rflag = False      # Do not display pretty print by default
version = "0.1"
cmd = "Usage: arcstat.py [-hvx] [-f fields] [-o file] [interval [count]]"
cur = {}
d = {}
out = None  
kstat = None
float_pobj = re.compile("^[0-9]+(\.[0-9]+)?$")


def kstat_update():
    global kstat

    p = Popen("/sbin/sysctl -q 'kstat.zfs.misc.arcstats'", stdin=PIPE,
        stdout=PIPE, stderr=PIPE, shell=True, close_fds=True)
    p.wait()
    
    k = p.communicate()[0].split('\n')
    if p.returncode != 0:
        sys.exit(1)

    if not k:
        sys.exit(1)

    kstat = {}

    for s in k:
        if not s: 
            continue

        s = s.strip() 

        name, value = s.split(':')
        name = name.strip()
        value = value.strip()

        parts = name.split('.')
        n = parts.pop()

        kstat[n] = Decimal(value)


def detailed_usage():
    print >> sys.stderr, "Arcstat version %s\n%s" % (version, cmd)
    print >> sys.stderr, "Field definitions are as follows\n"
    for key in cols:
        print >> sys.stderr, "%6s : %s" % (key, cols[key][1])
    print >> sys.stderr, "\nNote: K=10^3 M=10^6 G=10^9 and so on\n"
    sys.exit(1)


def usage():
    print >> sys.stderr, "Arcstat version %s\n%s" % (version, cmd)
    print >> sys.stderr, "\t -x : Print extended stats"
    print >> sys.stderr, "\t -f : Specify specific fields to print (see -v)"
    print >> sys.stderr, "\t -o : Print stats to file"
    print >> sys.stderr, "\t -r : Raw output"
    print >> sys.stderr, "\t -s : Specify a seperator\n\nExamples:"
    print >> sys.stderr, "\tarcstat -o /tmp/a.log 2 10"
    print >> sys.stderr, "\tarcstat -s , -o /tmp/a.log 2 10"
    print >> sys.stderr, "\tarcstat -v"
    print >> sys.stderr, "\tarcstat -f Time,Hit%,dh%,ph%,mh%"
    sys.exit(1)


def init():
    global sint
    global count
    global hdr 
    global xhdr 
    global opfile
    global sep
    global out

    desired_cols = None
    xflag = False
    hflag = False
    vflag = False
    i = 2

    try:
        opts, args = getopt.getopt
            sys.argv[1:],
            'xo:hvrs:f:',
            [
                'extended',
                'outfile',
                'help',
                'verbose',
                'raw',
                'seperator',
                'columns'
            ]
        )

    except getopt.error, msg:
        print >> sys.stderr, msg
        usage()

    for opt, arg in opts:
        if opt in ('-x', '--extended'):
            xflag = True
        if opt in ('-o', '--outfile'):
            opfile = arg 
        if opt in ('-h', '--help'):
            hflag = True
        if opt in ('-v', '--verbose'):
            vflag = True 
        if opt in ('-r', '--raw'):
            rflag = True 
        if opt in ('-s', '--seperator'):
            sep = arg
            i += 1
        if opt in ('-f', '--columns'):
            desired_cols = arg
            i += 1
        i += 1

    argv = sys.argv[i:]
    sint = int(argv[0]) if argv else sint
    count = int(argv[1]) if len(argv) > 1 else count

    if hflag or (xflag and desired_cols):
        usage()

    if vflag:
        detailed_usage()

    if xflag:
        hdr = xhdr

    if desired_cols:
        hdr = desired_cols.split(",")

        invalid = []
        for ele in hdr:
            if not cols.has_key(ele):
                invalid.append(ele)

        if len(invalid) > 0:
            print >> sys.stderr, "Invalid column definition! -- %s\n" % invalid
            usage() 

    if opfile:
        try: 
            out = open(opfile, "w")
            sys.stdout = out 

        except:
            print >> sys.stderr, "Cannot open %s for writing" % opfile
            sys.exit(1)


def snap_stats():
    global cur
    global kstat

    prev = copy.deepcopy(cur)
    kstat_update()

    cur = kstat
    for key in cur:
        if re.match(key, "class"):
            continue
        if prev.has_key(key):
            d[key] = cur[key] - prev[key]
        else:
            d[key] = cur[key]


def prettynum(sz, num=0):
    global rflag

    suffix = [' ', 'K', 'M', 'G', 'T', 'P', 'E', 'Z']
    index = 0

    if rflag or not float_pobj.match(str(num)):
        return "%*s" % (sz, num)

    while num >= 10000 and index < 8:
        num = num / 1000
        index += 1

    if index == 0: 
        return "%*d" % (sz, num)

    return "%*d%s" % (sz - 1, num, suffix[index])


def print_values():
    global hdr
    global sep
    global v

    for col in hdr:
        sys.stdout.write("%s%s" % (prettynum(cols[col][0], v[col]), sep))
    sys.stdout.write("\n")

def print_header():
    global hdr
    global sep

    for col in hdr:
        sys.stdout.write("%*s%s" % (cols[col][0], col, sep))
    sys.stdout.write("\n")

def calculate():
    global d
    global v

    v = {}
    v["Time"] = time.strftime("%H:%M:%S", time.localtime())
    v["hits"] = d["hits"] / sint
    v["miss"] = d["misses"] / sint
    v["read"] = v["hits"] + v["miss"]
    v["Hit%"] = 100 * v["hits"] / v["read"] if v["read"] > 0 else 0
    v["miss%"] = 100 - v["Hit%"] if v["read"] > 0 else 0
        
    v["dhit"] = (d["demand_data_hits"] + d["demand_metadata_hits"]) / sint
    v["dmis"] = (d["demand_data_misses"] + d["demand_metadata_misses"]) / sint
    v["dread"] = v["dhit"] + v["dmis"]
    v["dh%"] = 100 * v["dhit"] / v["dread"] if v["dread"] > 0 else 0
    v["dm%"] = 100 - v["dh%"] if v["dread"] > 0 else 0
        
    v["phit"] =(d["prefetch_data_hits"] + d["prefetch_metadata_hits"]) / sint
    v["pmis"] =(d["prefetch_data_misses"] + d["prefetch_metadata_misses"]) / sint
    v["pread"] = v["phit"] + v["pmis"]
    v["ph%"] = 100 * v["phit"] / v["pread"] if v["pread"] > 0 else 0
    v["pm%"] = 100 - v["ph%"] if v["pread"] > 0 else 0
        
    v["mhit"] = (d["prefetch_metadata_hits"] + d["demand_metadata_hits"]) / sint
    v["mmis"] = (d["prefetch_metadata_misses"] + d["demand_metadata_misses"]) / sint
    v["mread"] = v["mhit"] + v["mmis"]
    v["mh%"] = 100 * v["mhit"] / v["mread"] if v["mread"] > 0 else 0
    v["mm%"] = 100 - v["mh%"] if v["mread"] > 0 else 0
        
    v["size"] = cur["size"]
    v["tsize"] = cur["c"]
    v["mfu"] = d["hits"] / sint
    v["mru"] = d["mru_hits"] / sint
    v["mrug"] = d["mru_ghost_hits"] / sint
    v["mfug"] = d["mru_ghost_hits"] / sint
    v["eskip"] = d["evict_skip"] / sint
    v["rmiss"] = d["recycle_miss"] / sint
    v["mtxmis"] = d["mutex_miss"] / sint


def sighandler(*args):
    sys.exit(0)

def main():
    global sint
    global count
    global hdr_intr

    i = 0
    count_flag = 0

    init()
    if count > 0:
        count_flag = 1 

    signal(SIGINT, sighandler)
    while True:
        if i == 0:
            print_header()

        snap_stats()
        calculate()
        print_values()

        if count_flag == 1:
            if count <= 1:
                break
            count -= 1

        i = 0 if i == hdr_intr else i + 1
        time.sleep(sint)

    if out:
        out.close()


if __name__ == '__main__':
    main()
