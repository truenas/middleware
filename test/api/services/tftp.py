#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../conn/')
import conn

service = 'tftp'
headers = conn.headers
auth = conn.auth
payload = {
          "tftp_port": 75,
          "tftp_directory": "/mnt/tank0"
}
url = conn.url + 'services/' + service + '/' 

r = requests.put(url, auth = auth, data = json.dumps(payload), headers = headers)
#r = requests.get(url, auth = auth)
print r.status_code
result = json.loads(r.text)
for items in result:
  print items,':',result[items]


