#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../conn/')
import conn

service = 'afp'
headers = conn.headers
auth = conn.auth
payload = {
          "afp_srv_guest": True,
          "afp_srv_connections_limit": 60
}
url = conn.url + 'services/' + service + '/' 

r = requests.put(url, auth = auth, data = json.dumps(payload), headers = headers)

result = json.loads(r.text)
for items in result:
  print items,':',result[items]


