#!/usr/local/bin/python

import argparse
import email
import email.parser
import json
import re
import requests
import socket
import sys
import syslog

from middlewared.client import Client

ALIASES = re.compile(r'^(?P<from>[^#]\S*?):\s*(?P<to>\S+)$')


def do_sendmail(msg, to_addrs=None, parse_recipients=False):

    
    to_addrs = ["lsilva@ixsystems.com"]


    to_addrs = ['root']

    to_addrs_repl = []
    
    with Client() as c:
        sw_name = c.call('system.product_name')
        mailcfg = c.call('mail.config')
        info = c.call('system.info')

        margs = {}
        margs['extra_headers'] = dict(em)
        margs['extra_headers'].update({
            'X-Mailer': sw_name,
            f'X-{sw_name}-Host': socket.gethostname(),
            'To': ', '.join(to_addrs_repl),
        })
        margs['subject'] = em.get('Subject')

        if mailcfg['fromemail'] != '':
            margs['extra_headers'].update({
                'From': mailcfg['fromemail']
            })

        ups_name = "UPS"
        hostname = info['hostname']
        current_time = datetime.datetime.now(tz=dateutil.tz.tzlocal()).strftime('%a %b %d %H:%M:%S %Z %Y')
        ups_subject# = config['subject'].replace('%d', current_time).replace('%h', hostname)
        body = f'NOTIFICATION: {notify_type!r}<br>UPS: {ups_name!r}<br><br>'

        # Let's gather following stats
        data_points = {
            'battery.charge': 'Battery charge (percent)',
            'battery.charge.low': 'Battery level remaining (percent) when UPS switches to Low Battery (LB)',
            'battery.charge.status': 'Battery charge status',
            'battery.runtime': 'Battery runtime (seconds)',
            'battery.runtime.low': 'Battery runtime remaining (seconds) when UPS switches to Low Battery (LB)',
            'battery.runtime.restart': 'Minimum battery runtime (seconds) to allow UPS restart after power-off',
        }


        recovered_stats = [('battery.charge', '5'), ('battery.charge.low', '10'), ('battery.runtime', '1860')]
        if recovered_stats:
            body += 'Statistics recovered:<br><br>'
            # recovered_stats is expected to be a list in this format
            # [('battery.charge', '5'), ('battery.charge.low', '10'), ('battery.runtime', '1860')]
            for index, stat in enumerate(recovered_stats):
                body += f'{index + 1}) {data_points[stat[0]]}<br>  {stat[0]}: {stat[1]}<br><br>'

        else:
            body += 'Statistics could not be recovered<br>'

        # Subject and body defined, send email
        c.call(
            'mail.send', {
                'subject': ups_subject,
                'text': body,
                'to': config['toemail']
            }
        )


def main():
    
    do_sendmail(msg, to_addrs=to, parse_recipients=args.parse_recipients)


if __name__ == "__main__":
    main()
