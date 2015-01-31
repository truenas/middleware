#!/usr/local/bin/python

import requests
import json
import sys 
import conn
import os

os.system('rm *.pyc')
url = conn.url + 'network/staticroute/'
auth = conn.auth
headers = conn.headers
payload = {
          "sr_destination": "192.168.1.0/24",
          "sr_gateway": "192.168.3.1",
          "sr_description": "test route"
}

def get():
  print 'Getting network-staticroute ......'
  r = requests.get(url, auth = auth)
  if r.status_code == 200:
    result = json.loads(r.text)
    i = 0
    for i in range(0,len(result)):
      print ''
      for items in result[i]:
        print items+':', result[i][items]
    print '\nGet network-staticroute --> Succeeded!'
  else:
    print 'Get network-staticroute --> Failed!'

def post():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  if len(result) > 0:
    delete()
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 201:
    result = json.loads(r.text)
    print 'Create network-staticroute --> Succeeded!'
    return str(result['id'])+'/'
  else:
    print 'Create network-staticroute --> Failed!'

def put():
  id = post()
  r = requests.put(url+id, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 200:
    print 'Update network-staticroute --> Succeeded!'
  else:
    print 'Update network-staticroute --> Failed!'

def delete():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  for i in range(0,len(result)):
    r = requests.delete(url+str(result[i]['id'])+'/', auth = auth)
    if r.status_code == 204:
      print 'Delete network-staticroute --> Succeeded!'
    else:
      print 'Delete network-staticroute --> Failed!'
  if len(result) == 0:
    id = post()
    r = requests.delete(url+id, auth = auth)
    if r.status_code == 204:
      print 'Delete network-staticroute --> Succeeded!'
    else:
      print 'Delete network-staticroute --> Failed!'
