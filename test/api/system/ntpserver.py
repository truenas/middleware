#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../conn/')
import conn

headers = conn.headers
auth = conn.auth
url = conn.url + 'system/ntpserver/'
payload = {
          "ntp_minpoll": 6,
          "ntp_maxpoll": 10,
          "ntp_prefer": "false",
          "ntp_address": "br.pool.ntp.org",
          "ntp_burst": "false",
          "ntp_iburst": "true"
}

def ntpserver_get():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  for i in range(0,len(result)):
    print '\n'
    for items in result[i]:
      print items+':', result[i][items]

def ntpserver_post():
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':', result[items]

def ntpserver_put():
  id = raw_input('Input id:')+'/'
  r = requests.put(url+id, auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':', result[items] 

def ntpserver_delete():
  id = raw_input('Input id:')+'/' 
  r = requests.delete(url+id, auth = auth) 
  print r.status_code

def ntpserver_run():
  id = raw_input('Input id:')+'/'
  r = requests.post(url+id+'run/', auth = auth)
  print r.text

while(1):
  method = raw_input('Input method:')
  if method == 'get':
    ntpserver_get()
  elif method == 'post':
    ntpserver_post()
  elif method == 'put':
    ntpserver_put()
  elif method == 'delete':
    ntpserver_delete() 
