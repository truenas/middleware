#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../conn/')
import conn

auth = conn.auth
headers = conn.headers
url = conn.url + 'plugins/plugins/'
payload = {

}
payload2 = {

}

def jails_get():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  for i in range(0,len(result)):
    print '\n'
    for items in result[i]:
      print items+':', result[i][items]

def jails_post():
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  print r.text
  print r.status_code

while(1):
  method = raw_input('Input method:')
  if method == 'get':
    jails_get()
  elif method == 'post':
    jails_post()
