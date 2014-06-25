#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../conn/')
import conn

#vol_name = raw_input('Input volume name:')
url = conn.url + 'sharing/nfs/'
auth = conn.auth
headers = conn.headers
payload = {
          "nfs_comment": "My Test Share",
          "nfs_paths": ["/mnt/tank0"],
          "nfs_ro": "true",
          "nfs_mapall_user" : "root",
          "nfs_maproot_user" : "root",
          "nfs_mapall_group" : "wheel",
          "nfs_maproot_group" : "wheel"
}

def nfs_get():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  for i in range(0,len(result)):
    for items in result[i]:
      print items+':', result[i][items]

def nfs_post():
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':', result[items]

def nfs_put():
  id = raw_input('Input id:')+'/'
  r = requests.put(url+id, auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':', result[items]

def nfs_delete():
  id = raw_input('Input id:')+'/'
  r = requests.delete(url+id, auth = auth)
  print r.status_code

while (1):
  method = raw_input('Input method:')
  if method == 'get':
    nfs_get()
  elif method == 'post':
    nfs_post()
  elif method == 'delete':
    nfs_delete()
  elif method == 'put':
    nfs_put()
