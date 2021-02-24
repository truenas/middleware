import boto3
import time

from botocore import exceptions as boto_exceptions
from botocore.errorfactory import BaseClientExceptions as boto_BaseClientException

from middlewared.service import CallError

from .base import Authenticator
from .factory import auth_factory


class Route53Authenticator(Authenticator):

    NAME = 'route53'

    def initialize_credentials(self):
        self.access_key_id = self.attributes['access_key_id']
        self.secret_access_key = self.attributes['secret_access_key']

    def _validate_credentials(self, verrors):
        for k in ('secret_access_key', 'access_key_id'):
            if not getattr(self, k, None):
                verrors.add(k, 'Please provide a valid value.')

    def perform(self, domain, validation_name, validation_content):
        session = boto3.Session(
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
        )
        client = session.client('route53')

        # Finding zone id for the given domain
        paginator = client.get_paginator('list_hosted_zones')
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
                raise CallError(
                    f'Unable to find a Route53 hosted zone for {domain}'
                )
        except boto_exceptions.ClientError as e:
            raise CallError(
                f'Failed to get Hosted zones with provided credentials :{e}'
            )

        # Order the zones that are suffixes for our desired to domain by
        # length, this puts them in an order like:
        # ["foo.bar.baz.com", "bar.baz.com", "baz.com", "com"]
        # And then we choose the first one, which will be the most specific.
        zones.sort(key=lambda z: len(z[0]), reverse=True)
        zone_id = zones[0][1]

        try:
            resp = client.change_resource_record_sets(
                HostedZoneId=zone_id,
                ChangeBatch={
                    'Changes': [
                        {
                            'Action': 'UPSERT',
                            'ResourceRecordSet': {
                                'Name': validation_name,
                                'ResourceRecords': [{'Value': f'"{validation_content}"'}],
                                'TTL': 3600,
                                'Type': 'TXT'
                            }
                        }
                    ],
                    'Comment': 'TrueNAS-dns-route53 certificate validation'
                }
            )
        except boto_BaseClientException as e:
            raise CallError(f'Failed to update record sets : {e}')

        """
        Wait for a change to be propagated to all Route53 DNS servers.
        https://docs.aws.amazon.com/Route53/latest/APIReference/API_GetChange.html
        """
        for unused_n in range(0, 120):
            r = client.get_change(Id=resp['ChangeInfo']['Id'])
            if r['ChangeInfo']['Status'] == 'INSYNC':
                return resp['ChangeInfo']['Id']
            time.sleep(5)

        raise CallError(
            f'Timed out waiting for Route53 change. Current status: {resp["ChangeInfo"]["Status"]}'
        )

    def cleanup(self, *args, **kwargs):
        raise NotImplementedError


auth_factory.register(Route53Authenticator)
