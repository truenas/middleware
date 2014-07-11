#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../conn/')
import conn

auth = conn.auth
headers = conn.headers
url = conn.url + 'jails/templates/'
payload = {
    "jt_name": "NewTemplateTest",
    "jt_os": "FreeBSD",
    "jt_arch": "x86",
    "jt_url": "http://download.freenas.org/9.2.1.6/RELEASE/x64/jails/freenas-virtualbox-4.3.12.tgz"
}

def template_get():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  for i in range(0,len(result)):
    print '\n'
    for items in result[i]:
      print items+':', result[i][items]

def template_post():
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':', result[items]

def template_put():
  id = raw_input('Input id:')+'/'
  r = requests.put(url+id, auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':', result[items]

def template_delete():
  id = raw_input('Input id:')+'/'
  r = requests.delete(url+id, auth = auth)
  print r.status_code
  
while(1):
  method = raw_input('Input method:')
  if method == 'get':
    template_get()
  elif method == 'post':
    template_post()
  elif method == 'put':
    template_put()
  elif method == 'delete':
    template_delete()
