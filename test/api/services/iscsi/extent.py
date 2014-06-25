#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../../conn/')
import conn

service = 'extent'
headers = conn.headers
auth = conn.auth
payload = {
          "iscsi_target_extent_type": "File",
          "iscsi_target_extent_name": "extent1",
          "iscsi_target_extent_filesize": "10MB",
          "iscsi_target_extent_path": "/mnt/tank1/iscsi"
}

url = conn.url + 'services/iscsi/' + service + '/'

def extent_get():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0 
  for i in range(0,len(result)):
    print '\n'
    for items in result[i]:
      print items+':', result[i][items]

def extent_post():
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code != 201:
    print r.text
  elif r.status_code == 201:
    result = json.loads(r.text)
    for items in result:
      print items+':',result[items]

def extent_put():
  r = requests.put(url+'1/', auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':',result[items]

def extent_delete():
  r = requests.delete(url+'1/',auth = auth)
  print r.status_code

while(1):
  input = raw_input('Input method:')
  if input == 'put':
    extent_put()
  elif input == 'post':
    extent_post()
  elif input == 'delete':
    extent_delete()
  elif input == 'get':
    extent_get()
