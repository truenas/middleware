#!/usr/local/bin/python

import requests
import json
import sys 
sys.path.append('../conn/')
import conn


service = 'staticroute'
url = conn.url + 'network/' + service + '/'
auth = conn.auth
headers = conn.headers
payload = {
          "sr_destination": "192.168.1.0/24",
          "sr_gateway": "192.168.3.1",
          "sr_description": "test route"
}

def static_route_get():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  for i in range(0,len(result)):
    print '\n'
    for items in result[i]:
      print items+':', result[i][items]

def static_route_post():
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':', result[items]

def static_route_put():
  id = raw_input('Input id:')+'/'
  r = requests.put(url+id, auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':', result[items]

def static_route_delete():
  id = raw_input('Input id:')+'/'
  r = requests.delete(url+id, auth = auth)
  print r.status_code
  print r.text

while(1):
  method = raw_input('Input method:')
  if method == 'get':
    static_route_get()
  elif method == 'post':
    static_route_post()
  elif method == 'put':
    static_route_put()
  elif method == 'delete':
    static_route_delete()
