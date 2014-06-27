#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../../conn/')
import conn

service = 'authorizedinitiator'
headers = conn.headers
auth = conn.auth
payload = {
          "iscsi_target_initiator_initiators": "ALL",
          "iscsi_target_initiator_comment": "",
          "iscsi_target_initiator_auth_network": "192.168.3.0/24",
          "iscsi_target_initiator_tag": 1
}

url = conn.url + 'services/iscsi/' + service + '/'

def auth_init_get():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  for i in range(0,len(result)):
    for items in result[i]:
      print items+':', result[i][items]
    print '\n'

def auth_init_post():
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':', result[items]

def auth_init_put():
  id = raw_input('Input id:')
  r = requests.put(url+id+'/', auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':', result[items]

def auth_init_delete():
  id = raw_input('Input id:')
  r = requests.delete(url+id+'/', auth = auth)
  print r.status_code

while(1):
  input = raw_input('Input method:')
  if input == 'post':
    auth_init_post()
  elif input == 'get':
    auth_init_get()
  elif input == 'delete':
    auth_init_delete()  
  elif input == 'put':
    auth_init_put()
