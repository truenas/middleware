#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../../conn/')
import conn

service = 'portal'
headers = conn.headers
auth = conn.auth
payload = {
          "iscsi_target_portal_ips": [
                  "0.0.0.0:3260"
          ],
          "iscsi_target_portal_comment": ""
}

url = conn.url + 'services/iscsi/' + service + '/'

def portal_get():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  for i in range(0,len(result)):
    for items in result[i]:
      print items+':', result[i][items]
    print '\n'

def portal_post():
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':', result[items]

def portal_put():
  id = raw_input('Input id:')
  r = requests.put(url+id+'/', auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':', result[items]

def portal_delete():
  id = raw_input('Input id:')
  r = requests.delete(url+id+'/', auth = auth)
  print r.status_code

while(1):
  input = raw_input('Input method:')
  if input == 'post':
    portal_post()
  elif input == 'get':
    portal_get()
  elif input == 'delete':
    portal_delete()  
  elif input == 'put':
    portal_put()
