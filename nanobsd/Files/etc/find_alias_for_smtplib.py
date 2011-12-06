#!/usr/local/bin/python

import argparse
import email
import email.parser
import re
import sys

from django.core.management import setup_environ

sys.path.extend(["/usr/local/www", "/usr/local/www/freenasUI"])

from freenasUI import settings
setup_environ(settings)

from freenasUI.common.system import send_mail

ALIASES = re.compile(r'^(?P<from>[^#]\S+?):\s*(?P<to>\S+)$')

def do_sendmail(msg, to_addrs=None, parse_recipients=False):

    if to_addrs is None:
        if not parse_recipients:
            raise ValueError('Do not know who to send the message to.')
        to_addrs = []

    # XXX: this should probably be a FeedParser because reading from sys.stdin
    # is blocking.
    em_parser = email.parser.Parser()
    em = em_parser.parsestr(msg)
    if parse_recipients:
        # Strip away the comma based delimiters and whitespace.
        to_addrs = map(str.strip, em.get('To').split(','))

    if to_addrs:
        aliases = get_aliases()
        to_addrs_repl = []
        for to_addr in to_addrs:
            if to_addr.find('@') == -1 and to_addr in aliases:
                to_addr = aliases[to_addr]
            to_addrs_repl.append(to_addr)

    margs = {}
    margs['extra_headers'] = dict(em)
    margs['subject'] = em.get('Subject')
    margs['text'] = ''.join(email.iterators.body_line_iterator(em))
    if to_addrs_repl:
        margs['to'] = to_addrs_repl

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
            for key, val in aliases.iteritems():
                if val in aliases:
                    aliases[key] = aliases[val]
                    doround = True
        return aliases

def main():
    parser = argparse.ArgumentParser(description='Process email')
    parser.add_argument('-i', dest='strip_leading_dot', action='store_false',
                        default=True, help='see sendmail(8) -i')
    parser.add_argument('-t', dest='parse_recipients', action='store_true',
                        default=False,
                        help='parse recipients from message')
    parser.usage  = ' '.join(parser.format_usage().split(' ')[1:-1])
    parser.usage += ' [email_addr|user] ..'
    args, to = parser.parse_known_args()
    if not to and not args.parse_recipients:
        parser.exit(message=parser.format_usage())
    msg = sys.stdin.read()
    do_sendmail(msg, to_addrs=to, parse_recipients=args.parse_recipients)

if __name__ == "__main__":
    main()
