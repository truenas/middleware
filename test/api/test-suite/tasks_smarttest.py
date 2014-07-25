#!/usr/local/bin/python

import requests
import json
import sys
import conn

headers = conn.headers
auth = conn.auth
url = conn.url + 'tasks/smarttest/'
payload = {
          "smarttest_disks": [1, 4],
          "smarttest_type": "L",
          "smarttest_hour": "*",
          "smarttest_daymonth": "*",
          "smarttest_month": "*",
          "smarttest_dayweek": "*",
          "smarttest_desc": ""
}

def get():
  print 'Getting tasks-smarttest ......'
  r = requests.get(url, auth = auth)
  if r.status_code == 200:
    result = json.loads(r.text)
    i = 0
    for i in range(0,len(result)):
      print '\n'
      for items in result[i]:
        print items+':', result[i][items]
    print 'Get tasks-smarttest --> Succeeded!'
  else:
    print 'Get tasks-smarttest --> Failed!'

def post():
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 201:
    result = json.loads(r.text)
    print 'Create tasks-smarttest --> Succeeded!'
    return str(result['id'])+'/'
  else:                                                                      
    print 'Create tasks-smarttest --> Failed!'

def put():
  id = post()
  r = requests.put(url+id, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 200:
    print 'Update tasks-smarttest --> Succeeded!'
  else:
    print 'Update tasks-smarttest --> Failed!'

def delete():
  id = post()
  r = requests.delete(url+id, auth = auth)
  if r.status_code == 204:
    print 'Delete tasks-smarttest --> Succeeded!'
  else:
    print 'Delete tasks-smarttest --> Failed!'

