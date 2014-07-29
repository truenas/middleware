#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../conn/')
import conn

vol_name = raw_input('Input volume name:')
url = conn.url+'storage/volume/'+vol_name+'/datasets/'
auth = conn.auth
headers = conn.headers
payload = {
  "avail": "2.44G",
  "mountpoint": "/mnt/"+vol_name+"/foo",
  "name": "foo",
  "pool": "tank",
  "refer": "144K",
  "used": "144K"
}

def dataset_get():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  for i in range(0,len(result)):
    for items in result[i]:
      print items+':', result[i][items]

def dataset_post():
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+'/', result[items]

def dataset_delete():
  r = requests.delete(url+'foo/', auth = auth)
  print r.status_code

while (1):
  method = raw_input('Input method:')
  if method == 'get':
    dataset_get()
  elif method == 'post':
    dataset_post()
  elif method == 'delete':
    dataset_delete()
