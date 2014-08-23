#!/usr/local/bin/python

import requests
import json
import sys 
import conn
import os

os.system('rm *.pyc')
url = conn.url + 'network/vlan/'
auth = conn.auth
headers = conn.headers
payload = {
          "vlan_vint": "vlan0",
          "vlan_pint": "em0",
          "vlan_tag": 0
}

def get():
  print 'Getting network-vlan ......'
  r = requests.get(url, auth = auth)
  if r.status_code == 200:
    result = json.loads(r.text)
    i = 0
    for i in range(0,len(result)):
      print ''
      for items in result[i]:
        print items+':', result[i][items]
    print '\nGet network-vlan --> Succeeded!'
  else:
    print 'Get network-vlan --> Failed!'

def post():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  if len(result) > 0:
    delete()
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 201:
    result = json.loads(r.text)
    print 'Create network-vlan --> Succeeded!'
    return str(result['id'])+'/'
  else:
    print 'Create network-vlan --> Failed!'

def put():
  id = post()
  r = requests.put(url+id, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 200:
    print 'Update network-vlan --> Succeeded!'
  else:
    print 'Update network-vlan --> Failed!'

def delete():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  for i in range(0,len(result)):
    r = requests.delete(url+str(result[i]['id'])+'/', auth = auth)
    if r.status_code == 204:
      print 'Delete network-vlan --> Succeeded!'
    else:
      print 'Delete network-vlan --> Failed!'
  if len(result) == 0:
    id = post()
    r = requests.delete(url+id, auth = auth)
    if r.status_code == 204:
      print 'Delete network-vlan --> Succeeded!'
    else:
      print 'Delete network-vlan --> Failed!'
