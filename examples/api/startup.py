import argparse
import json
import sys

import oauth2


class Startup(object):

    def __init__(self, hostname, name, secret):
        self._hostname = hostname
        self._name = name
        self._secret = secret

        self._consumer = oauth2.Consumer(key=name, secret=secret)
        self._client = oauth2.Client(self._consumer)

        self._ep = 'http://%s/api/v1.0' % hostname

    def request(self, resource, method='GET', data=None):
        if data is None:
            data = ''
        resp, content = self._client.request(
            '%s/%s/' % (self._ep, resource),
            method=method,
            body=json.dumps(data),
            headers={'Content-Type': "application/json"}
        )
        return json.loads(content)

    def _get_disks(self):
        disks = self.request('storage/disk')
        return [disk['disk_name'] for disk in disks]

    def create_pool(self):
        self.request('storage/volume', method='POST', data={
            'volume_name': 'tank',
            'layout': [
                {'vdevtype': 'stripe', 'disks': self._get_disks()},
            ],
        })

    def create_dataset(self):
        self.request('storage/volume/tank/datasets', method='POST', data={
            'name': 'MyShare',
        })

    def create_cifs_share(self):
        self.request('sharing/cifs_share', method='POST', data={
            'cifs_name': 'My Test Share',
            'cifs_path': '/mnt/tank/MyShare',
            'cifs_guestonly': True
        })

    def service_start(self, name):
        self.request('services/services/%s' % name, method='PUT', data={
            'srv_enable': True,
        })

    def run(self):
        self.create_pool()
        self.create_dataset()
        self.create_cifs_share()
        self.service_start('cifs')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-H', '--hostname', required=True, type=str)
    parser.add_argument('-n', '--name', required=True, type=str)
    parser.add_argument('-s', '--secret', required=True, type=str)

    args = parser.parse_args(sys.argv[1:])

    startup = Startup(args.hostname, args.name, args.secret)
    startup.run()

if __name__ == '__main__':
    main()
