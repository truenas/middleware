#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../conn/')
import conn

service = 'nt4'
headers = conn.headers
auth = conn.auth
payload = {
          "nt4_adminname": "admin",
          "nt4_dcname": "mydcname",
          "nt4_workgroup": "WORKGROUP",
          "nt4_netbiosname": "netbios",
          "nt4_adminpw": "mypw"
}
url = conn.url + 'services/' + service + '/' 

#r = requests.get(url, auth = auth)
r = requests.put(url, auth = auth, data = json.dumps(payload), headers = headers)

result = json.loads(r.text)
for items in result:
  print items,':',result[items]


