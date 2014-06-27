#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../conn/')
import conn

headers = conn.headers
auth = conn.auth
url = conn.url + 'system/rsync/'
payload = {
          "rsync_user": "root",
          "rsync_minute": "*/20",
          "rsync_enabled": "true",
          "rsync_daymonth": "*",
          "rsync_path": "/mnt/tank0",
          "rsync_delete": "false",
          "rsync_hour": "*",
          "id": 1,
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

def rsync_get():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  for i in range(0,len(result)):
    print '\n'
    for items in result[i]:
      print items+':', result[i][items]

def rsync_post():
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':', result[items]

def rsync_put():
  id = raw_input('Input id:')+'/'
  r = requests.put(url+id, auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':', result[items] 

def rsync_delete():
  id = raw_input('Input id:')+'/' 
  r = requests.delete(url+id, auth = auth) 
  print r.status_code

def rsync_run():
  id = raw_input('Input id:')+'/'
  r = requests.post(url+id+'run/', auth = auth)
  print r.text

while(1):
  method = raw_input('Input method:')
  if method == 'get':
    rsync_get()
  elif method == 'post':
    rsync_post()
  elif method == 'put':
    rsync_put()
  elif method == 'delete':
    rsync_delete() 
  elif method == 'run':
    rsync_run()
