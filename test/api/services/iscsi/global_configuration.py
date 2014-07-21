#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../../conn/')
import conn

service = 'globalconfiguration'
headers = conn.headers
auth = conn.auth
payload = {
          "iscsi_discoveryauthmethod": "None",
          "iscsi_basename": "iqn.2011-03.org.example.istgt",
}

url = conn.url + 'services/iscsi/' + service + '/1/'
r = requests.put(url, auth = auth, data = json.dumps(payload), headers = headers)
print r.status_code
result = json.loads(r.text)
for items in result:
  print items+':',result[items]
r = requests.get(url, auth = auth)
result = json.loads(r.text)
#for items in result:
#  print items+':',result[items]
