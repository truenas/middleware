#!/usr/local/bin/python

import requests
import json
import sys
import os
import conn
import extra_functions
import storage_volume

os.system('rm *.pyc')
if extra_functions.volume_check() == False:
  storage_volume.post()
headers = conn.headers
auth = conn.auth
url = conn.url + 'tasks/rsync/'
payload = {
          "rsync_user": "root",
          "rsync_minute": "*/20",
          "rsync_enabled": "true",
          "rsync_daymonth": "*",
          "rsync_path": "/mnt/new_volume_test_suite",
          "rsync_delete": "false",
          "rsync_hour": "*",
          "rsync_extra": "",
          "rsync_archive": "true",
          "rsync_compress": "true",
          "rsync_dayweek": "*",
          "rsync_desc": "",
          "rsync_direction": "push",
          "rsync_times": "true",
          "rsync_preserveattr": "false",
          "rsync_remotehost": "testhost",
          "rsync_mode": "module",
          "rsync_remotemodule": "testmodule",
          "rsync_remotepath": "",
          "rsync_quiet": "false",
          "rsync_recursive": "true",
          "rsync_month": "*",
          "rsync_preserveperm": "false",
          "rsync_remoteport": 22
}

def get():
  print 'Getting tasks-rsync ......'
  r = requests.get(url, auth = auth)
  if r.status_code == 200:
    result = json.loads(r.text)
    i = 0
    for i in range(0,len(result)):
      for items in result[i]:
        print items+':', result[i][items]
      print '\n'
    print 'Get tasks-rsync --> Succeeded!'
  else:
    print 'Get tasks-rsync --> Failed!'

def post():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  if len(result) > 0:
    delete() 
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 201:
    result = json.loads(r.text)
    print 'Create tasks-rsync --> Succeeded!'
    return str(result['id'])+'/'
  else:
    print 'Create tasks-rsync --> Failed!'
    return ''

def put():
  id = post()
  r = requests.put(url+id, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 200:
    print 'Update tasks-rsync --> Succeeded!'
  else:
    print 'Update tasks-rsync --> Failed!'

def delete():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)  
  i = 0
  for i in range(0,len(result)):
    r = requests.delete(url+str(result[i]['id'])+'/', auth = auth)
    if r.status_code == 204:
      print 'Delete tasks-rsync --> Succeeded!'
    else:
      print 'Delete tasks-rsync --> Failed!'
  if len(result) == 0:
    id = post()
    r = requests.delete(url+id, auth = auth)
    if r.status_code == 204:
      print 'Delete tasks-rsync --> Succeeded!'
    else:
      print 'Delete tasks-rsync --> Failed!'

def run():
  id = post()
  r = requests.post(url+id+'run/', auth = auth)
  if r.status_code == 202:
    print 'Rsync is running ...... --> Succeeded!'
  else:
    print 'Rsync is not running --> Failed!'
