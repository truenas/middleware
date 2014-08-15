#!/usr/local/bin/python

import requests
import json
import sys
import conn
import storage_volume
import storage_task
import extra_functions
import os

os.system('rm *.pyc')
if extra_functions.volume_check() == False:
  storage_volume.post()
if extra_functions.task_check() == False:
  storage_task.post()

url = conn.url + 'storage/replication/'
auth = conn.auth
headers = conn.headers
payload = {
          "repl_filesystem": "new_volume_test_suite",
          "repl_zfs": "new_volume_test_suite",
          "repl_remote_hostkey":"AAAA",
          "repl_remote_hostname":"testhost",
          "repl_remote_cipher": "standard"
}

def get():
  print 'Getting storage-replication ......'
  r = requests.get(url, auth = auth)
  if r.status_code == 200:
    result = json.loads(r.text)
    i = 0
    for i in range(0,len(result)):
      print ''
      for items in result[i]:
        print items+':', result[i][items]
    print '\nGet storage-replication --> Succeeded!'
  else:
    print 'Get storage-replication --> Failed!'

def post():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  if len(result)>0:
    delete()
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 201:
    result = json.loads(r.text)
    print 'Create storage-replication --> Succeeded!'
    return str(result['id'])+'/'
  else:
    print 'Create storage-replication --> Failed!'
    return 'fail'

def put():
  id = post()
  r = requests.put(url+id, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 200:
    print 'Update storage-replication --> Succeeded!'
  else:
    print 'Update storage-replication --> Failed!'

def delete():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  if len(result)>0:
    for i in range(0,len(result)):
      r = requests.delete(url+str(result[i]['id'])+'/', auth = auth)
      if r.status_code == 204:
        print 'Delete storage-replication --> Succeeded!'
      else:
        print 'Delete storage-replication --> Failed!'
  else:
    id = post()
    r = requests.delete(url+id, auth = auth)
    if r.status_code == 204:
      print 'Delete storage-replication --> Succeeded!'
    else:
      print 'Delete storage-replication --> Failed!'

