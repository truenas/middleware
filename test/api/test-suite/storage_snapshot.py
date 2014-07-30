#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../conn/')
import conn

url = conn.url+'storage/snapshot/'
auth = conn.auth
headers = conn.headers
payload = {
          "dataset": "tank0",
          "name": "test0"
}

def snapshot_get():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  for i in range(0,len(result)):
    for items in result[i]:
      print items+':', result[i][items]

def snapshot_post():
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+'/', result[items]

def snapshot_delete():
  id = raw_input('Input id:')+'/'
  r = requests.delete(url+id, auth = auth)
  print r.status_code

while (1):
  method = raw_input('Input method:')
  if method == 'get':
    snapshot_get()
  elif method == 'post':
    snapshot_post()
  elif method == 'delete':
    snapshot_delete()
