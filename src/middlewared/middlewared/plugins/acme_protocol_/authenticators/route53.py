import errno

import boto3
import time

from botocore import exceptions as boto_exceptions

from middlewared.schema import accepts, Dict, Str
from middlewared.service import CallError

from .base import Authenticator


class Route53Authenticator(Authenticator):

    NAME = 'route53'
    SCHEMA = Dict(
        'route53',
        Str('access_key_id', required=True, empty=False, title='Access Key Id'),
        Str('secret_access_key', required=True, empty=False, title='Secret Access Key'),
    )

    def initialize_credentials(self):
        self.access_key_id = self.attributes['access_key_id']
        self.secret_access_key = self.attributes['secret_access_key']
        self.client = boto3.Session(
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
        ).client('route53')

    @staticmethod
    @accepts(SCHEMA)
    def validate_credentials(data):
        pass

    def _perform(self, domain, validation_name, validation_content):
        return self._change_txt_record('UPSERT', validation_name, validation_content)

    def wait_for_records_to_propagate(self, resp_change_info):
        """
        Wait for a change to be propagated to all Route53 DNS servers.
        https://docs.aws.amazon.com/Route53/latest/APIReference/API_GetChange.html
        """
        r = resp_change_info
        for unused_n in range(0, 120):
            r = self.client.get_change(Id=resp_change_info['Id'])
            if r['ChangeInfo']['Status'] == 'INSYNC':
                return resp_change_info['Id']
            time.sleep(5)

        raise CallError(f'Timed out waiting for Route53 change. Current status: {r["Status"]}')

    def _find_zone_id_for_domain(self, domain):
        # Finding zone id for the given domain
        paginator = self.client.get_paginator('list_hosted_zones')
        target_labels = domain.rstrip('.').split('.')
        zones = []
        try:
            for page in paginator.paginate():
                for zone in page['HostedZones']:
                    if zone['Config']['PrivateZone']:
                        continue

                    candidate_labels = zone['Name'].rstrip('.').split('.')
                    if candidate_labels == target_labels[-len(candidate_labels):]:
                        zones.append((zone['Name'], zone['Id']))
            if not zones:
                raise CallError(f'Unable to find a Route53 hosted zone for {domain}', errno=errno.ENOENT)
        except boto_exceptions.ClientError as e:
            raise CallError(f'Failed to get Hosted zones with provided credentials :{e}')

        # Order the zones that are suffixes for our desired to domain by
        # length, this puts them in an order like:
        # ["foo.bar.baz.com", "bar.baz.com", "baz.com", "com"]
        # And then we choose the first one, which will be the most specific.
        zones.sort(key=lambda z: len(z[0]), reverse=True)
        return zones[0][1]

    def _change_txt_record(self, action, validation_domain_name, validation):
        if action not in ('UPSERT', 'DELETE'):
            raise CallError('Please specify a valid action for changing TXT record for Route53')

        zone_id = self._find_zone_id_for_domain(validation_domain_name)
        try:
            response = self.client.change_resource_record_sets(
                HostedZoneId=zone_id,
                ChangeBatch={
                    'Comment': 'TrueNAS-dns-route53 certificate validation ' + action,
                    'Changes': [
                        {
                            'Action': action,
                            'ResourceRecordSet': {
                                'Name': validation_domain_name,
                                'Type': 'TXT',
                                'TTL': 10,
                                'ResourceRecords': [{'Value': f'"{validation}"'}],
                            }
                        }
                    ]
                }
            )
            return response['ChangeInfo']
        except Exception as e:
            raise CallError(f'Failed to {action} Route53 record sets: {e}')

    def _cleanup(self, domain, validation_name, validation_content):
        self._change_txt_record('DELETE', validation_name, validation_content)
