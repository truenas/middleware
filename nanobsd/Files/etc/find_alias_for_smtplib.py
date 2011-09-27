#!/usr/local/bin/python

import argparse
from django.core.management import setup_environ
import os
import re
import sys

sys.path.extend(["/usr/local/www", "/usr/local/www/freenasUI"])

from freenasUI import settings
setup_environ(settings)

from django.db import models
from freenasUI.common.system import send_mail

ALIASES = re.compile(r'^(?P<from>[^#]\S+?):\s*(?P<to>\S+)$')

def do_sendmail(msg, to=None, plain=False):
    headers = {}
    _headers, text = msg.split('\n\n', 1)
    for header in _headers.split('\n'):
        name, val = header.split(': ', 1)
        headers[name] = val

    to = headers.get("To", to)
    if to and '@' not in to:
        aliases = get_aliases()
        if to in aliases:
            headers['To'] = aliases[to]

    margs = {}
    if plain:
        margs['text'] = msg
        margs['plain'] = True 
    else:
        margs['text'] = text
        margs['extra_headers'] = headers
    if to:
        margs['to'] = to

    send_mail(**margs)

def get_aliases():
    with open('/etc/aliases', 'r') as f:
        aliases = {}

        for line in f.readlines():
            search = ALIASES.search(line)
            if search:
                _from, _to = search.groups()
                aliases[_from] = _to

        doround = True
        while True:
            if not doround:
                break
            else:
                doround = False
            for key,val in aliases.items():
                if val in aliases:
                    aliases[key] = aliases[val]
                    doround = True
        return aliases

def main():
    parser = argparse.ArgumentParser(description='Process email.')
    parser.add_argument('-i', dest='to', metavar='N', type=str,
                       help='to email address')
    parser.add_argument('-t', dest='plain', action='store_true',
                       help='read recipients')
    args = parser.parse_args()
    msg = sys.stdin.read()
    do_sendmail(msg, to=args.to, plain=args.plain)

if __name__ == "__main__":
    main()
