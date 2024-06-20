import argparse
import email
import email.parser
import json
import os
import re
import requests
import sys
import syslog

from truenas_api_client import Client

ALIASES = re.compile(r'^(?P<from>[^#]\S*?):\s*(?P<to>\S+)$')


def do_sendmail(msg, to_addrs=None, parse_recipients=False):

    if to_addrs is None:
        if not parse_recipients:
            syslog.syslog('Do not know who to send the message to.' + msg[0:140])
            raise ValueError('Do not know who to send the message to.')
        to_addrs = []

    # XXX: this should probably be a FeedParser because reading from sys.stdin
    # is blocking.
    em_parser = email.parser.Parser()
    em = em_parser.parsestr(msg)
    if parse_recipients:
        # Strip away the comma based delimiters and whitespace.
        to_addrs = list(map(str.strip, em.get('To').split(',')))

    if not to_addrs or not to_addrs[0]:
        to_addrs = ['root']

    to_addrs_repl = []
    if to_addrs:
        aliases = get_aliases()
        for to_addr in to_addrs:
            for to_addr in to_addr.split(','):
                if to_addr.find('@') != -1:
                    to_addrs_repl.append(to_addr)
                elif to_addr.find('@') == -1 and to_addr in aliases:
                    to_addrs_repl.append(aliases[to_addr])

    if not to_addrs_repl:
        syslog.syslog(f'No aliases found to send email to {", ".join(to_addrs)}')
        sys.exit(1)

    with Client() as c:
        sw_name = 'TrueNAS'

        margs = {}
        margs['extra_headers'] = dict(em)
        margs['extra_headers'].update({
            'X-Mailer': sw_name,
            f'X-{sw_name}-Host': c.call('system.hostname'),
            'To': ', '.join(to_addrs_repl),
        })
        margs['subject'] = em.get('Subject')

        if em.is_multipart():
            attachments = [part for part in em.walk() if part.get_content_maintype() != 'multipart']
            margs['attachments'] = True if attachments else False
            margs['text'] = (
                'This is a MIME formatted message.  If you see '
                'this text it means that your email software '
                'does not support MIME formatted messages.')
            margs['html'] = None
        else:
            margs['text'] = ''.join(email.iterators.body_line_iterator(em))

        margs['to'] = to_addrs_repl

        if not margs.get('attachments'):
            c.call('mail.send', margs)
        else:
            token = c.call('auth.generate_token')
            files = []
            for attachment in attachments:
                entry = {'headers': []}
                for k, v in attachment.items():
                    entry['headers'].append({'name': k, 'value': v})
                entry['content'] = attachment.get_payload()
                files.append(entry)

            requests.post(
                f'http://localhost:6000/_upload?auth_token={token}',
                files={
                    'data': json.dumps({'method': 'mail.send', 'params': [margs]}),
                    'file': json.dumps(files),
                },
            )


def get_aliases():
    with open('/etc/aliases', 'r') as f:
        aliases = {}

        for line in f.readlines():
            search = ALIASES.search(line)
            if search:
                _from, _to = search.groups()
                aliases[_from] = _to

        while True:
            oldaliases = set(aliases.items())
            for key, val in aliases.items():
                if key == val:
                    syslog.syslog(syslog.LOG_ERR, f'Found a recursive dependency for {key}')
                elif val in aliases:
                    aliases[key] = aliases[val]
            if set(aliases.items()) == oldaliases:
                break
        return aliases


def main():
    syslog.openlog(logoption=syslog.LOG_PID, facility=syslog.LOG_MAIL)
    parser = argparse.ArgumentParser(description='Process email')
    parser.add_argument('-i', dest='strip_leading_dot', action='store_false',
                        default=True, help='see sendmail(8) -i')
    parser.add_argument('-t', dest='parse_recipients', action='store_true',
                        default=False,
                        help='parse recipients from message')
    parser.usage = ' '.join(parser.format_usage().split(' ')[1:-1])
    parser.usage += ' [email_addr|user] ..'
    args, to = parser.parse_known_args()
    if not to and not args.parse_recipients:
        parser.exit(message=parser.format_usage())
    msg = sys.stdin.read()
    syslog.syslog("sending mail to " + ', '.join(to) + '\n' + msg[0:140])
    do_sendmail(msg, to_addrs=to, parse_recipients=args.parse_recipients)


if __name__ == "__main__":
    main()
