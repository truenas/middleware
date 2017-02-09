#!/usr/local/bin/python


import argparse
import time
import gzip
import bz2
import json
import re
import pprint
import subprocess
import os

import traceback
import struct
import hashlib

from time import gmtime, strftime
from datetime import datetime
from pyparsing import Word, alphas, Suppress, Combine, nums, string, Optional, Regex


class Parser(object):
    def __init__(self):
        ints = Word(nums)
        # priority
        # priority = Suppress("<") + ints + Suppress(">")
        # timestamp
        month = Word(string.uppercase, string.lowercase, exact=3)
        day = ints
        hour = ints + Suppress(":")
        min = ints + Suppress(":")
        sec = ints

        timestamp = month + day + hour + min + sec
        # hostname
        hostname = Word(alphas + nums + "_" + "-" + ".")

        # appname
        appname = Word(alphas + nums + "/" + "-" + "_" + ".") + Optional(Suppress("[") + ints + Suppress("]")) + Suppress(":")

        # message
        message = Regex(".*")

        # pattern build
        self.__pattern = timestamp + hostname + appname + message

        self.t = datetime.today()
        self.year = self.t.year
        self.tz = str(time.tzname[time.daylight])

    def parse(self, line):
        parsed = self.__pattern.parseString(line)
        dstr = "{:04}-{}-{:02} {:02}:{:02}:{:02} {}".format(
            int(self.year),
            str(parsed[0]),
            int(parsed[1]),
            int(parsed[2]),
            int(parsed[3]),
            int(parsed[4]),
            str(self.tz))

        d = time.strptime(dstr, "%Y-%b-%d %H:%M:%S %Z")
        payload = {}
        payload["timestamp"] = int(time.mktime(d))

        payload["timestamp_raw"] = parsed[0] + " " + parsed[1] + " " + parsed[2] + ":" + parsed[3] + ":" +  parsed[4]
        payload["hostname"] = parsed[5]
        payload["program"] = parsed[6]

        try:
            payload["pid"] = parsed[7]
            payload["text"] = parsed[8]
        except IndexError:
            payload["text"] = parsed[7]
            payload["pid"] = -1
        return payload



def dmisha256_v1():
    global data

    keywords = [
        'dmi-system-uuid',
        'dmi-system-serial-number',
        'dmi-baseboard-product-name',
        'dmi-system-product-name',
        'dmi-baseboard-serial-number',
        'dmi-baseboard-manufacturer',
        'dmi-baseboard-product-name',
        'dmi-chassis-serial-number',
        'dmi-processor-serial-number',
        'dmi-memory-serial-number'
    ]
    hashStr = ''
    s = struct.Struct('64s')
    for kw in keywords:
        if kw == 'dmi-memory-serial-number' and data[kw] == '__NOTSET__':
            data[kw] = ''            
        buffer = s.pack(str(data[kw]))
        hashStr = hashStr + buffer
    sha256 = hashlib.sha256(hashStr).hexdigest()
    return sha256

def parseDMILine(line):
    global inBlock, whichBlock, whichBlock2, data, skipTerms, goodBlocks, fieldsToCap
    rePatField = re.compile('^.*: (.*)$')
    
    p = line.split()
    try:
        p[0]
    except:
        return
    if inBlock:
        if p[0] != "Handle":
            for field in list(fieldsToCap[whichBlock].keys()):
                if p[0] == field:
                    if whichBlock == "System" and whichBlock2 != 'Information':
                        continue;
                    m = rePatField.match(line)
                    dataLoc = fieldsToCap[whichBlock][field]
                    if whichBlock == "Memory":
                        if not m.group(1).rstrip("\r\n\x02 ").lstrip() == 'NO DIMM' and data[dataLoc] == '__NOTSET__':
                            data[dataLoc] = m.group(1).rstrip("\r\n\x02 ").lstrip()
                    else:
                        if data[dataLoc] == '':
                            data[dataLoc] = m.group(1).rstrip("\r\n\x02 ").lstrip()
        else:
            inBlock = 0
    for t in skipTerms:
        if p[0] == t:
            return
    for t in goodBlocks:
        if p[0] == t:
            inBlock = 1
            whichBlock = t
            whichBlock2 = p[1]


def parseDMI(dmioutput):
    global inBlock, whichBlock, whichBlock2, data, skipTerms, goodBlocks, fieldsToCap
    OKS=0
    ERRORS=0
    skipTerms = [
    '#',
    'Handle',
    'Table',        
    ]    
    goodBlocks = [
    'System',
    'Base',
    'Chassis',
    'Processor',
    'Memory',
    ]    
    fieldsToCap = { }
    fieldsToCap['System'] = { }
    fieldsToCap['Base'] = { }
    fieldsToCap['Chassis'] = { }
    fieldsToCap['Processor'] = { }
    fieldsToCap['Memory'] = { }
    
    fieldsToCap['System']['Product'] = 'dmi-system-product-name'
    fieldsToCap['System']['UUID:'] = 'dmi-system-uuid'
    fieldsToCap['System']['Serial'] = 'dmi-system-serial-number'
    
    fieldsToCap['Base']['Product'] = 'dmi-baseboard-product-name'
    fieldsToCap['Base']['Serial'] = 'dmi-baseboard-serial-number'
    fieldsToCap['Base']['Manufacturer:'] = 'dmi-baseboard-manufacturer'
    
    fieldsToCap['Chassis']['Serial'] = 'dmi-chassis-serial-number'
    fieldsToCap['Processor']['Serial'] = 'dmi-processor-serial-number'
    fieldsToCap['Memory']['Serial'] = 'dmi-memory-serial-number'
    
    inBlock = 0
    whichBlock = ''
    whichBlock2 = ''

    data = {}
    data['dmi-system-uuid'] = ''
    data['dmi-system-serial-number'] = ''
    data['dmi-system-product-name'] = ''
    data['dmi-baseboard-product-name'] = ''
    data['dmi-baseboard-serial-number'] = ''
    data['dmi-baseboard-manufacturer'] = ''
    data['dmi-chassis-serial-number'] = ''
    data['dmi-processor-serial-number'] = ''
    data['dmi-memory-serial-number'] = '__NOTSET__'

    for line in dmioutput.splitlines():
        parseDMILine(line)
    data['dmi-sha256'] = dmisha256_v1()
    return data




""" --------------------------------- """


def main():
    log = {
        'telemetry' : {
            'type': 'main',
            'version': 2,
        },
        'filecontents': {},
        'cmdout': {},
    }


    files_to_log = [
        '/data/license',
        '/etc/version',
        '/etc/hostid',
    ]

    cmds_to_log = {
        'zpool_list': ['/sbin/zpool', 'list'],
        'zfs_list': ['/sbin/zfs', 'list'],
        'zfs_get_all': ['/sbin/zfs', 'get', '-t', 'filesystem', 'type,creation,used,available,referenced,compressratio,recordsize,checksum,compression,copies,dedup,refcompressratio' ],
        'arc_summary': ['/usr/local/bin/arc_summary.py', ''],
        'dmidecode': ['/usr/local/sbin/dmidecode', ''],
        'kstat_zfs': [ '/sbin/sysctl', 'kstat.zfs' ],
        'uname': ['/usr/bin/uname', '-a'],
        'ipmitoolsdr': ['/usr/local/bin/ipmitool', '-c' , 'sdr' ],
        'ipmitoolsel': ['/usr/local/bin/ipmitool', '-c' , 'sel', 'elist' ],
        
    }


    filters = {
        'zfsd':
        {
            'all': 1,
            'p': [],
        },

        'smartd': {
            'all': 0,
            'p': [
                '^Device:'
                ],
        },

        'kernel': {
            'all': 0,
            'p': [
                'Invalidating pack',
                'MEDIUM ERROR',
                'UNIT ATTENTION',
                'MCA: CPU',
                'link state',
                '^carp',
                'exited on signal',
                'out of swap space',
                'swap_pager',
                ],

            },

    }


    parser = argparse.ArgumentParser(description='Gather and stage data for sending to ix Systems.')

    parser.add_argument('files', metavar='files', type=str, nargs='+', help='File to read, txt or gz, will auto-dectect')
    parser.add_argument('--debug', action='store_true',  help="Debug/Verbose output")

    args = parser.parse_args()
    now = time.time()


    for cmdname in cmds_to_log:
        if args.debug:
            print("[DEBUG]: cmdname = " + cmdname)
        try:
            if args.debug:
                print("[DEBUG]: running " + cmdname)
            log['cmdout'][cmdname] = subprocess.check_output(cmds_to_log[cmdname], stderr=subprocess.STDOUT)
            if cmdname == 'dmidecode':
                if args.debug:
                    print("[DEBUG]: running parseDMI " + cmdname)
                log['dmi'] = parseDMI(log['cmdout'][cmdname])
                log['dmi']['dmi-sha256'] = dmisha256_v1()
                if args.debug:
                    print("[DEBUG]: writing dmisha " + cmdname)
                f = open("/tmp/dmisha.txt", "w")
                f.write(log['dmi']['dmi-sha256'])
                f.close()                
#           log['cmdout'][cmdname] = ''
        except:
            log['cmdout'][cmdname] = 'Error Running Command'
            if args.debug:
                var = traceback.format_exc().splitlines()
                print(var)
            continue

    for f in files_to_log:
        try:
            fd = open(f, 'rb')
            log['filecontents'][f] = fd.read()
            fd.close()
        except:
            log['filecontents'][f] = "ERROR opening or reading file."
            continue


    bzf = bz2.BZ2File('/var/log/telemetry.json.bz2', 'wb')
    json.dump(log, bzf)
    bzf.write("\n")

    del log

    for file in args.files:
        mtime = os.path.getmtime(str(file))
        if ( (now - mtime) > (48*60*60) ):
            continue
        if file.endswith('.gz'):
            file = gzip.GzipFile(file)
        elif file.endswith('.bz2'):
            file = bz2.BZ2File(file)
        else:
            file = open(file)

        parser = Parser()

        with file as syslogFile:
            for line in syslogFile:
                try:
                    pl = parser.parse(line)
                except:
                    continue
                pl['telemetry'] = { 'type': 'syslog', 'version': 2 }
                if ( (now - pl['timestamp']) > (24*60*60) ):
                    continue
                for f in filters:
                    if pl['program'] == f:
                        if filters[f]['all'] == 1:
                            json.dump(pl, bzf)
                            bzf.write("\n")
                        else:
                            for pat in filters[f]['p']:
                                if re.search(pat, pl['text']):
                                    json.dump(pl, bzf)
                                    bzf.write("\n")

    bzf.close()

if __name__ == "__main__":
  main()
