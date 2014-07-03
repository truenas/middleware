#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../conn/')
import conn

headers = conn.headers
auth = conn.auth
payload = {
          "tun_var": "xhci_load_whatever",
          "tun_comment": "",
          "tun_value": "YES",
          "tun_enabled": True
}

url = conn.url + 'system/tunable/'

def tunable_get():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  for i in range(0,len(result)):
    print '\n'
    for items in result[i]:
      print items+':',result[i][items]

def tunable_post():
#if(1==1):
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':',result[items]

def tunable_put():
  id = raw_input('Input id need to update:')
  r = requests.put(url+id+'/', auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':',result[items]

def tunable_delete():
  id = raw_input('Input id need to delete:')
  r = requests.delete(url+id+'/',auth = auth)
  print r.status_code

while(1):
  input = raw_input('Input method:')
  if input == 'get':
    tunable_get()
  elif input == 'put':
    tunable_put()
  elif input == 'post':
    tunable_post()
  elif input == 'delete':
    tunable_delete()
