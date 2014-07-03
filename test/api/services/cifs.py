#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../conn/')
import conn

service = 'cifs'
headers = conn.headers
auth = conn.auth
payload = {
"cifs_srv_hostlookup": "false"
}
url = conn.url + 'services/' + service + '/' 

#r = requests.put(url, auth = auth, data = json.dumps(payload), headers = headers)
r = requests.get(url, auth = auth)
result = json.loads(r.text)
for items in result:
  print items,':',result[items]


