#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../../conn/')
import conn

service = 'targettoextent'
headers = conn.headers
auth = conn.auth
payload = {
          "iscsi_target": 1,
          "iscsi_extent": 1,
          "iscsi_lunid": 'null'
}

url = conn.url + 'services/iscsi/' + service + '/'

def target_to_extent_get():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  for i in range(0,len(result)):
    for items in result[i]:
      print items+':', result[i][items]
    print '\n'

def target_to_extent_post():
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':', result[items]

def target_to_extent_put():
  id = raw_input('Input id:')
  r = requests.put(url+id+'/', auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':', result[items]

def target_to_extent_delete():
  id = raw_input('Input id:')
  r = requests.delete(url+id+'/', auth = auth)
  print r.status_code

while(1):
  input = raw_input('Input method:')
  if input == 'post':
    target_to_extent_post()
  elif input == 'get':
    target_to_extent_get()
  elif input == 'delete':
    target_to_extent_delete()  
  elif input == 'put':
    target_to_extent_put()
