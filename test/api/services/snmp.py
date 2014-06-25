#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../conn/')
import conn

service = 'snmp'
headers = conn.headers
auth = conn.auth
payload = {
          "snmp_contact": "admin@freenas.org",
          "snmp_traps": False,
          "id": 1
}
url = conn.url + 'services/' + service + '/' 

r = requests.put(url, auth = auth, data = json.dumps(payload), headers = headers)

result = json.loads(r.text)
for items in result:
  print items,':',result[items]


