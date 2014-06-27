#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../conn/')
import conn

headers = conn.headers
auth = conn.auth
payload = {
          "sysctl_mib": "net.inet.tcp.rfc1323",
          "sysctl_comment": "",
          "sysctl_value": "20",
          "sysctl_enabled": True
}

url = conn.url + 'system/sysctl/'

def sysctl_get():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  for i in range(0,len(result)):
    print '\n'
    for items in result[i]:
      print items+':',result[i][items]

def sysctl_post():
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':',result[items]

def sysctl_put():
  id = raw_input('Input id need to update:')
  r = requests.put(url+id+'/', auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':',result[items]

def sysctl_delete():
  id = raw_input('Input id need to delete:')
  r = requests.delete(url+id+'/',auth = auth)
  print r.status_code

while(1):
  input = raw_input('Input method:')
  if input == 'get':
    sysctl_get()
  elif input == 'put':
    sysctl_put()
  elif input == 'post':
    sysctl_post()
  elif input == 'delete':
    sysctl_delete()
