#!/usr/local/bin/python

import requests
import json
import sys
import conn
import os

os.system('rm *.pyc')
headers = conn.headers
auth = conn.auth
url = conn.url + 'system/tunable/'
payload = {
          "tun_var": "new_tunable_test_suite",
          "tun_comment": "",
          "tun_value": "YES",
          "tun_enabled": True
}

def get():
  print 'Getting system-tunable ......'
  r = requests.get(url, auth = auth)
  if r.status_code == 200:
    result = json.loads(r.text)
    i = 0
    for i in range(0,len(result)):
      print ''
      for items in result[i]:
        print items+':', result[i][items]
    print '\nGet system-tunable --> Succeeded!'
  else:
    print 'Get system-tunable --> Failed!'

def post():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  if len(result) > 0:
    delete()
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 201:
    result = json.loads(r.text)
    print 'Create system-tunable --> Succeeded!'
    return str(result['id'])+'/'
  else:
    print 'Create system-tunable --> Failed!'

def put():
  id = post()
  r = requests.put(url+id, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 200:
    print 'Update system-tunable --> Succeeded!'
  else:
    print 'Update system-tunable --> Failed!'

def delete():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  for i in range(0,len(result)):
    r = requests.delete(url+str(result[i]['id'])+'/', auth = auth)
    if r.status_code == 204:
      print 'Delete system-tunable --> Succeeded!'
    else:
      print 'Delete system-tunable --> Failed!'
  if len(result) == 0:
    id = post()
    r = requests.delete(url+id, auth = auth)
    if r.status_code == 204:
      print 'Delete system-tunable --> Succeeded!'
    else:
      print 'Delete system-tunable --> Failed!'

