#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../conn/')
import conn

#vol_name = raw_input('Input volume name:')
url = conn.url + 'storage/replication/'
auth = conn.auth
headers = conn.headers
payload = {
          "repl_filesystem": "tank0",
          "repl_zfs": "tank0",
          "repl_remote_hostname": "testhost",
          "repl_remote_hostkey": "AAAA"
}

def replication_get():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  for i in range(0,len(result)):
    for items in result[i]:
      print items+':', result[i][items]

def replication_post():
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':', result[items]

def replication_put():
  id = raw_input('Input id:')+'/'
  r = requests.put(url+id, auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':', result[items]

def replication_delete():
  id = raw_input('Input id:')+'/'
  r = requests.delete(url+id, auth = auth)
  print r.status_code

while (1):
  method = raw_input('Input method:')
  if method == 'get':
    replication_get()
  elif method == 'post':
    replication_post()
  elif method == 'delete':
    replication_delete()
  elif method == 'put':
    replication_put()
