#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../../conn/')
import conn

service = 'target'
headers = conn.headers
auth = conn.auth
payload = {
          "iscsi_target_logical_blocksize": 512,
          "iscsi_target_portalgroup": 'null',
          "iscsi_target_initialdigest": "Auto",
          "iscsi_target_queue_depth": 32,
          "iscsi_target_name": "target",
          "iscsi_target_initiatorgroup": 1,
          "iscsi_target_alias": 'null',
          "iscsi_target_type": "Disk",
          "iscsi_target_authgroup": 'null',
          "iscsi_target_authtype": "Auto",
          "iscsi_target_serial": "10000001",
          "iscsi_target_flags": "rw"
}

url = conn.url + 'services/iscsi/' + service + '/'

def target_get():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  for i in range(0,len(result)):
    for items in result[i]:
      print items+':', result[i][items]
    print '\n'

def target_post():
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':', result[items]

def target_put():
  id = raw_input('Input id:')
  r = requests.put(url+id+'/', auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':', result[items]

def target_delete():
  id = raw_input('Input id:')
  r = requests.delete(url+id+'/', auth = auth)
  print r.status_code

while(1):
  input = raw_input('Input method:')
  if input == 'post':
    target_post()
  elif input == 'get':
    target_get()
  elif input == 'delete':
    target_delete()  
  elif input == 'put':
    target_put()
