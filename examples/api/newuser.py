import requests

r = requests.post(
    'https://freenas.mydomain/api/v1.0/account/bsdusers/',
    auth=('root', 'freenas'),
    headers={'Content-Type': 'application/json'},
    data={
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
print r.text
