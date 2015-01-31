#!/usr/local/bin/python

import requests
import json
import sys
import os
import conn
import storage_disk

disk_id = storage_disk.get_id()
headers = conn.headers
auth = conn.auth
url = conn.url + 'tasks/smarttest/'
payload = {
          "smarttest_disks": [disk_id],
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
      for items in result[i]:
        print items+':', result[i][items]
      print '\n'
    print 'Get tasks-smarttest --> Succeeded!'
  else:
    print 'Get tasks-smarttest --> Failed!'

def post():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  if len(result) > 0:
    delete()
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 201:
    result = json.loads(r.text)
    print 'Create tasks-smarttest --> Succeeded!'
    return str(result['id'])+'/'
  else:                                                                      
    print 'Create tasks-smarttest --> Failed!'
    return ''    

def put():
  id = post()
  r = requests.put(url+id, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 200:
    print 'Update tasks-smarttest --> Succeeded!'
  else:
    print 'Update tasks-smarttest --> Failed!'

def delete():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  for i in range(0,len(result)):
    r = requests.delete(url+str(result[i]['id'])+'/', auth = auth)
    if r.status_code == 204:
      print 'Delete tasks-smarttest --> Succeeded!'
    else:
      print 'Delete tasks-smarttest --> Failed!'
  if len(result) == 0:
    id = post()
    r = requests.delete(url+id, auth = auth)
    if r.status_code == 204:
      print 'Delete tasks-smarttest --> Succeeded!'
    else:
      print 'Delete tasks-smarttest --> Failed!'
