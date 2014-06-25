#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../conn/')
import conn

headers = conn.headers
auth = conn.auth
payload = {
          "srv_enable": True
}
url = conn.url + 'services/services/'

def services_get():
  r = requests.get(url, auth = auth)
  print r.text
  result = json.loads(r.text)
  i = 0
  for i in range(0,len(result)):
    print '\n'
    for items in result[i]:
      print items,':',result[i][items]

def services_put():
  input = raw_input('Input id/name:')+'/'
  status = raw_input('True or False?')
  r = requests.put(url+input, auth = auth, data = json.dumps({"srv_enable": status}), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':', result[items]

while(1):
  method = raw_input('Input method:')
  if method == 'put':
    services_put()
  elif method == 'get':
    services_get()
