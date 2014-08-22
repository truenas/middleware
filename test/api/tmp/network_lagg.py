#!/usr/local/bin/python

import requests
import json
import sys 
sys.path.append('../conn/')
import conn


service = 'lagg'
url = conn.url + 'network/' + service + '/'
auth = conn.auth
headers = conn.headers
payload = {
          "lagg_interfaces": ["em0"],
          "lagg_protocol": "roundrobin"
}

def lagg_get():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  for i in range(0,len(result)):
    print '\n'
    for items in result[i]:
      print items+':', result[i][items]

def lagg_post():
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':', result[items]

def lagg_delete():
  id = raw_input('Input id:')+'/'
  r = requests.delete(url+id, auth = auth)
  print r.status_code

while(1):
  method = raw_input('Input method:')
  if method == 'get':
    lagg_get()
  elif method == 'post':
    lagg_post()
  elif method == 'put':
    lagg_put()
  elif method == 'delete':
    lagg_delete()
