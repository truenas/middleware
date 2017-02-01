#!/usr/local/bin/python
import argparse
from middlewared.client import Client
from middlewared.client.utils import Struct


class RCDServiceMonitoring(object):

    def ad_monitor(self, client, option):
        ad = Struct(client.call('datastore.query', 'directoryservice.activedirectory', None, {'get': True}))
        if ad.ad_enable_monitor and ad.ad_enable:
            if option == 'start':
                return client.call('notifier.enable_test_service_connection', ad.ad_monitor_frequency, ad.ad_recover_retry, ad.ad_domainname, 3268, 'activedirectory')
            elif option == 'stop':
                return client.call('notifier.disable_test_service_connection', ad.ad_monitor_frequency, ad.ad_recover_retry, ad.ad_domainname, 3268, 'activedirectory')


def main(option):
    client = Client()
    rcd = RCDServiceMonitoring()
    rcd.ad_monitor(client, option)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("option", choices=['start', 'stop'], help="Control middlewared monitor services")

    args = parser.parse_args()
    main(args.option)
