#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../conn/')
import conn

#vol_name = raw_input('Input volume name:')
url = conn.url + 'sharing/cifs/'
auth = conn.auth
headers = conn.headers
payload = {
          "cifs_name": "My Test Share",
          "cifs_path": "/mnt/tank0"
}

def cifs_get():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  for i in range(0,len(result)):
    for items in result[i]:
      print items+':', result[i][items]

def cifs_post():
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':', result[items]

def cifs_put():
  id = raw_input('Input id:')+'/'
  r = requests.put(url+id, auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':', result[items]

def cifs_delete():
  id = raw_input('Input id:')+'/'
  r = requests.delete(url+id, auth = auth)
  print r.status_code

while (1):
  method = raw_input('Input method:')
  if method == 'get':
    cifs_get()
  elif method == 'post':
    cifs_post()
  elif method == 'delete':
    cifs_delete()
  elif method == 'put':
    cifs_put()
