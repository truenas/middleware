#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../../conn/')
import conn

service = 'authcredential'
headers = conn.headers
auth = conn.auth
payload = {
          "iscsi_target_auth_secret": "secret",
          "iscsi_target_auth_peeruser": "peeruser",
          "iscsi_target_auth_peersecret": "peersecret",
          "iscsi_target_auth_user": "user",
          "iscsi_target_auth_tag": 1,
}

url = conn.url + 'services/iscsi/' + service + '/'

def auth_cred_get():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  for i in range(0,len(result)):
    for items in result[i]:
      print items+':', result[i][items]
    print '\n'

def auth_cred_post():
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':', result[items]

def auth_cred_put():
  id = raw_input('Input id:')
  r = requests.put(url+id+'/', auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':', result[items]

def auth_cred_delete():
  id = raw_input('Input id:')
  r = requests.delete(url+id+'/', auth = auth)
  print r.status_code

while(1):
  input = raw_input('Input method:')
  if input == 'post':
    auth_cred_post()
  elif input == 'get':
    auth_cred_get()
  elif input == 'delete':
    auth_cred_delete()  
  elif input == 'put':
    auth_cred_put()
