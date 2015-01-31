#!/usr/local/bin/python

import requests
import json
import sys
import conn
import storage_volume
import extra_functions
import os

os.system('rm *.pyc')
if extra_functions.volume_check() == False:
  storage_volume.post()
url = conn.url+'storage/snapshot/'
auth = conn.auth
headers = conn.headers
payload = {
          "dataset": "new_volume_test_suite",
          "name": "new_snapshot_test_suite"
}

def get():
  print 'Getting storage-snapshot ......'
  r = requests.get(url, auth = auth)
  if r.status_code == 200:
    result = json.loads(r.text)
    i = 0
    for i in range(0,len(result)):
      print ''
      for items in result[i]:
        print items+':', result[i][items]
    print '\nGet storage-snapshot --> Succeeded!'
  else:
    print 'Get storage-snapshot --> Failed!'

def post():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  if len(result)>0:
    delete()
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 201:
    result = json.loads(r.text)
    print 'Create storage-snapshot --> Succeeded!'
    return str(result['fullname'])+'/'
  else:
    print 'Create storage-snapshot --> Failed!'
    return 'fail'

def put():
  print 'No PUT function for storage-snapshot!'

def delete():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  if len(result)>0:
    for i in range(0,len(result)):
      r = requests.delete(url+str(result[i]['fullname'])+'/', auth = auth)
      if r.status_code == 204:
        print 'Delete storage-snapshot --> Succeeded!'
      else:
        print 'Delete storage-snapshot --> Failed!'
  else:
    id = post()
    r = requests.delete(url+id, auth = auth)
    if r.status_code == 204:
      print 'Delete storage-snapshot --> Succeeded!'
    else:
      print r.text
      print 'Delete storage-snapshot --> Failed!'

