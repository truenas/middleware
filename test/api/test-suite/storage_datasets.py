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
url = conn.url+'storage/volume/new_volume_test_suite/datasets/'
auth = conn.auth
headers = conn.headers
payload = {
  "avail": "2.44G",
  "mountpoint": "/mnt/new_volume_test_suite/new_datasets_test_suite",
  "name": "new_datasets_test_suite",
  "pool": "new_volume_test_suite",
  "refer": "144K",
  "used": "144K"
}

def get():
  print 'Getting storage_datasets ......'
  r = requests.get(url, auth = auth)
  if r.status_code == 200:
    result = json.loads(r.text)
    i = 0
    for i in range(0,len(result)):
      print ''
      for items in result[i]:
        print items+':', result[i][items]
    print '\nGet storage_datasets --> Succeeded!'
  else:
    print 'Get storage_datasets --> Failed!'

def post():
  if 'new_datasets_test_suite' in get_list():
    delete()
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 201:
    result = json.loads(r.text)
    print 'Create storage_datasets --> Succeeded!'
    return str(result['name'])+'/'
  else:
    print 'Create storage_datasets --> Failed!'

def put():
  print 'No PUT function for storage_datasets!'

def delete():
  if 'new_datasets_test_suite' not in get_list():
    name = post()
  r = requests.delete(url+'new_datasets_test_suite/', auth = auth)
  if r.status_code == 204:
    print 'Delete storage_datasets --> Succeeded!'
  else:
    print 'Delete storage_datasets --> Failed!'

def get_list():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  datasets_list = []
  for i in range(0,len(result)):
    datasets_list.append(result[i]['name'])
  return datasets_list
