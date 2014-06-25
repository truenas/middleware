#!/usr/local/bin/python

import requests
import json
import sys
sys.path.append('../conn/')
import conn

headers = conn.headers
auth = conn.auth
payload = {
          "smarttest_disks": [1, 4],
          "smarttest_type": "L",
          "smarttest_hour": "*",
          "smarttest_daymonth": "*",
          "smarttest_month": "*",
          "smarttest_dayweek": "*",
          "smarttest_desc": ""
}

url = conn.url + 'system/smarttest/'

def smarttest_get():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  for i in range(0,len(result)):
    print '\n'
    for items in result[i]:
      print items+':',result[i][items]

def smarttest_post():
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':',result[items]

def smarttest_put():
  id = raw_input('Input id need to update:')
  r = requests.put(url+id+'/', auth = auth, data = json.dumps(payload), headers = headers)
  result = json.loads(r.text)
  for items in result:
    print items+':',result[items]

def smarttest_delete():
  id = raw_input('Input id need to delete:')
  r = requests.delete(url+id+'/',auth = auth)
  print r.status_code

while(1):
  input = raw_input('Input method:')
  if input == 'get':
    smarttest_get()
  elif input == 'put':
    smarttest_put()
  elif input == 'post':
    smarttest_post()
  elif input == 'delete':
    smarttest_delete()
