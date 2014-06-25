#!/usr/local/bin/python

import requests
import json
import sys 
sys.path.append('../conn/')
import conn


service = 'vlan'
url = conn.url + 'network/' + service + '/'
auth = conn.auth
headers = conn.headers
payload = {
          "vlan_vint": "vlan0",
          "vlan_pint": "em0",
          "vlan_tag": 0
}

def vlan_get():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  for i in range(0,len(result)):
    print '\n'
    for items in result[i]:
      print items+':', result[i][items]

def vlan_post():
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':', result[items]

def vlan_put():
  id = raw_input('Input id:')+'/'
  r = requests.put(url+id, auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':', result[items]

def vlan_delete():
  id = raw_input('Input id:')+'/'
  r = requests.delete(url+id, auth = auth)
  print r.status_code

while(1):
  method = raw_input('Input method:')
  if method == 'get':
    vlan_get()
  elif method == 'post':
    vlan_post()
  elif method == 'put':
    vlan_put()
  elif method == 'delete':
    vlan_delete()
