#!/usr/local/bin/python

import requests
import json
import sys
import conn
import os
import extra_functions

if extra_functions.volume_check() == False:
  import storage_volume
  storage_volume.post()

os.system('rm *.pyc')
headers = conn.headers
auth = conn.auth
url = conn.url + 'sharing/afp/'
payload = {
          "afp_name": "New_AFP_Share_test_suite",
          "afp_path": "/mnt/new_volume_test_suite"
}

def get():
  print 'Getting sharing-afp ......'
  r = requests.get(url, auth = auth)
  if r.status_code == 200:
    result = json.loads(r.text)
    i = 0
    for i in range(0,len(result)):
      print ''
      for items in result[i]:
        print items+':', result[i][items]
    print '\nGet sharing-afp --> Succeeded!'
  else:
    print 'Get sharing-afp --> Failed!'

def post():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  if len(result) > 0:
    delete()
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 201:
    result = json.loads(r.text)
    print 'Create sharing-afp --> Succeeded!'
    return str(result['id'])+'/'
  else:
    print 'Create sharing-afp --> Failed!'

def put():
  id = post()
  r = requests.put(url+id, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 200:
    print 'Update sharing-afp --> Succeeded!'
  else:
    print 'Update sharing-afp --> Failed!'

def delete():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  for i in range(0,len(result)):
    r = requests.delete(url+str(result[i]['id'])+'/', auth = auth)
    if r.status_code == 204:
      print 'Delete sharing-afp --> Succeeded!'
    else:
      print 'Delete sharing-afp --> Failed!'
  if len(result) == 0:
    id = post()
    r = requests.delete(url+id, auth = auth)
    if r.status_code == 204:
      print 'Delete sharing-afp --> Succeeded!'
    else:
      print 'Delete sharing-afp --> Failed!'
