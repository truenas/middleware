#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../conn/')
import conn

service = 'lldp'
headers = conn.headers
auth = conn.auth
payload = {
          "lldp_intdesc": "false"
}
url = conn.url + 'services/' + service + '/' 

#r = requests.get(url, auth = auth)
r = requests.put(url, auth = auth, data = json.dumps(payload), headers = headers)

result = json.loads(r.text)
for items in result:
  print items,':',result[items]


