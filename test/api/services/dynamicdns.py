#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../conn/')
import conn

service = 'dynamicdns'
headers = conn.headers
auth = conn.auth
payload = {
          "ddns_provider": "dyndns@dyndns.org",
          "ddns_username": "admin"
}
url = conn.url + 'services/' + service + '/'

r = requests.put(url, auth = auth, data = json.dumps(payload), headers = headers)

result = json.loads(r.text)
for items in result:
  print items,':',result[items]


