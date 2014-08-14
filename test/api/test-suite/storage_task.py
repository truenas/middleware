#!/usr/local/bin/python

import requests
import json
import sys
import os
import conn
import extra_functions
import storage_volume

if extra_functions.volume_check() == False:
  storage_volume.post()
url = conn.url + 'storage/task/'
auth = conn.auth
headers = conn.headers
payload = {
          "task_filesystem": "new_volume_test_suite",
          "task_recursive": "false",
          "task_ret_unit": "week",
          "task_interval": 30
}

def get():
  print 'Getting storage-task ......'
  r = requests.get(url, auth = auth)
  if r.status_code == 200:
    result = json.loads(r.text)
    i = 0
    for i in range(0,len(result)):
      print ''
      for items in result[i]:
        print items+':', result[i][items]
    print '\nGet storage-task --> Succeeded!'
  else:
    print 'Get storage-task --> Failed!'

def post():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  if len(result)>0:
    delete()
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 201:
    result = json.loads(r.text)
    print 'Create storage-task --> Succeeded!'
    return str(result['id'])+'/'
  else:
    print 'Create storage-task --> Failed!'
    return 'fail'

def put():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  if len(result)>0:
    delete()
  id = post()
  r = requests.put(url+id, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 200:
    print 'Update storage-task --> Succeeded!'
  else:
    print 'Update storage-task --> Failed!'

def delete():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  if len(result)>0:
    for i in range(0,len(result)):
      r = requests.delete(url+str(result[i]['id'])+'/', auth = auth)
      if r.status_code == 204:
        print 'Delete storage-task --> Succeeded!'
      else:
        print 'Delete storage-task --> Failed!'
  else:
    id = post()
    r = requests.delete(url+id, auth = auth)
    if r.status_code == 204:
      print 'Delete storage-task --> Succeeded!'
    else:
      print 'Delete storage-task --> Failed!'
