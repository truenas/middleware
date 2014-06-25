#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../conn/')
import conn

service = 'globalconfiguration'
url = conn.url + 'network/' + service + '/'
auth = conn.auth
headers = conn.headers
payload = {
          "gc_domain": "local",
          "gc_ipv4gateway": "10.5.0.1",
          "gc_hostname": "freenas",
          "gc_netwait_enabled": "false",
          "gc_hosts": "",
          "gc_ipv6gateway": "",
          "gc_netwait_ip": "",
          "gc_nameserver1": "192.168.3.1",
          "gc_nameserver3": "",
          "gc_nameserver2": "",
          "gc_httpproxy": ""
}

def interface_get():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  for items in result:
    print items+':', result[items]

def interface_put():
  id = raw_input('Input id:')+'/'
  r = requests.put(url+id, auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':', result[items]

while(1):
  method = raw_input('Input method:')
  if method == 'get':
    interface_get()
  elif method == 'put':
    interface_put()
