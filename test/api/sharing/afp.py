#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../conn/')
import conn

#vol_name = raw_input('Input volume name:')
url = conn.url + 'sharing/afp/'
auth = conn.auth
headers = conn.headers
payload = {
          "afp_name": "My Test Share",
          "afp_path": "/mnt/tank0"
}

def afp_get():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  for i in range(0,len(result)):
    for items in result[i]:
      print items+':', result[i][items]

def afp_post():
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':', result[items]

def afp_put():
  id = raw_input('Input id:')+'/'
  r = requests.put(url+id, auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':', result[items]

def afp_delete():
  id = raw_input('Input id:')+'/'
  r = requests.delete(url+id, auth = auth)
  print r.status_code

while (1):
  method = raw_input('Input method:')
  if method == 'get':
    afp_get()
  elif method == 'post':
    afp_post()
  elif method == 'delete':
    afp_delete()
  elif method == 'put':
    afp_put()
