#!/usr/local/bin/python


import argparse
import time
import gzip
import bz2
import json
import re
import pprint
import subprocess

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

""" --------------------------------- """


def main():
    log = {
        'syslog': [],
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
        'zfs_get_all': ['/sbin/zfs', 'get', 'all'],
        'arc_summary': ['/usr/local/bin/arc_summary.py', ''],
        'dmidecode': ['/usr/local/sbin/dmidecode', ''],
        'uname': ['/usr/bin/uname', '-a'],
        
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

    args = parser.parse_args()


    for file in args.files:
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
                for f in filters:
                    if pl['program'] == f:
                        if filters[f]['all'] == 1:
                            log['syslog'].append(pl)
                        else:
                            for pat in filters[f]['p']:
                                if re.search(pat, pl['text']):
                                    log['syslog'].append(pl)

    for cmdname in cmds_to_log:
        try:
            log['cmdout'][cmdname] = subprocess.check_output(cmds_to_log[cmdname])
#           log['cmdout'][cmdname] = ''
        except:
            log['cmdout'][cmdname] = 'Error Running Command'
            continue

    for f in files_to_log:
        try:
            fd = open(f, 'rb')
            log['filecontents'][f] = fd.read()
            fd.close()
        except:
            log['filecontents'][f] = "ERROR opening or reading file."
            continue


    f = bz2.BZ2File('/var/log/telemetry.json.bz2', 'wb')
    json.dump(log, f)
    f.close()


if __name__ == "__main__":
  main()
