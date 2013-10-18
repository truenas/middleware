import json
import oauth2

consumer = oauth2.Consumer(
    key='myclient',
    secret='886e8991d4ae9a010656921b1011f2c400348d1d643edbc807c429bb30168b8a55670f9f22cf68610c0a9e277dd69151c48c15c18aa2dccb8bf8b057ca1187c1',
)
client = oauth2.Client(consumer)

content = client.request(
    'http://freenas.mydomain/api/v1.0/account/bsdusers/',
    method='POST',
    headers={'Content-Type': 'application/json'},
    body=json.dumps({
        'bsdusr_uid': '1100',
        'bsdusr_username': 'myuser',
        'bsdusr_mode': '755',
        'bsdusr_creategroup': True,
        'bsdusr_password': '12345',
        'bsdusr_shell': '/usr/local/bin/bash',
        'bsdusr_full_name': 'Full Name',
        'bsdusr_email': 'name@provider.com',
    })
)
