#!/usr/local/bin/python

import requests
import json
import sys 
import conn
import os

os.system('rm *.pyc')
url = conn.url + 'network/interface/'
auth = conn.auth
headers = conn.headers
payload = {
          "int_ipv4address": "10.5.32.12",
          "int_name": "ext",
          "int_v4netmaskbit": "24",
          "int_interface": "em0"
}

def get():
  print 'Getting network-interface ......'
  r = requests.get(url, auth = auth)
  if r.status_code == 200:
    result = json.loads(r.text)
    i = 0
    for i in range(0,len(result)):
      print ''
      for items in result[i]:
        print items+':', result[i][items]
    print '\nGet network-interface --> Succeeded!'
  else:
    print 'Get network-interface --> Failed!'

def post():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  if len(result) > 0:
    delete()
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 201:
    result = json.loads(r.text)
    print 'Create network-interface --> Succeeded!'
    return str(result['id'])+'/'
  else:
    print 'Create network-interface --> Failed!'

def put():
  id = post()
  r = requests.put(url+id, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 200:
    print 'Update network-interface --> Succeeded!'
  else:
    print 'Update network-interface --> Failed!'

def delete():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  for i in range(0,len(result)):
    r = requests.delete(url+str(result[i]['id'])+'/', auth = auth)
    if r.status_code == 204:
      print 'Delete network-interface --> Succeeded!'
    else:
      print 'Delete network-interface --> Failed!'
  if len(result) == 0:
    id = post()
    r = requests.delete(url+id, auth = auth)
    if r.status_code == 204:
      print 'Delete network-interface --> Succeeded!'
    else:
      print 'Delete network-interface --> Failed!'
