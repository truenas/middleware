#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../conn/')
import conn

#vol_name = raw_input('Input volume name:')
url = conn.url + 'storage/disk/'
auth = conn.auth
headers = conn.headers
payload = {
          "disk_togglesmart": "true"
}

def replication_get():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  for i in range(0,len(result)):
    print '\n'
    for items in result[i]:
      print items+':', result[i][items]

def replication_put():
  id = raw_input('Input id:')+'/'
  r = requests.put(url+id, auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':', result[items]

while (1):
  method = raw_input('Input method:')
  if method == 'get':
    replication_get()
  elif method == 'put':
    replication_put()
