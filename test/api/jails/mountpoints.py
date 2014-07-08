#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../conn/')
import conn

auth = conn.auth
headers = conn.headers
url = conn.url + 'jails/mountpoints/'
payload = {
    "destination": "/mnt",
    "fstype": "nullfs",
    "jail": "transmission_1",
    "mounted": "true",
    "readonly": "false",
    "source": "/mnt/tank0/test"
}

def mountpoint_get():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  for i in range(0,len(result)):
    print '\n'
    for items in result[i]:
      print items+':', result[i][items]

def mountpoint_post():
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':', result[items]

def mountpoint_put():
  id = raw_input('Input id:')+'/'
  r = requests.put(url+id, auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':', result[items]

def mountpoint_delete():
  id = raw_input('Input id:')+'/'
  r = requests.delete(url+id, auth = auth)
  print r.status_code
  
while(1):
  method = raw_input('Input method:')
  if method == 'get':
    mountpoint_get()
  elif method == 'post':
    mountpoint_post()
  elif method == 'put':
    mountpoint_put()
