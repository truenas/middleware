#!/usr/local/bin/python

import requests
import json
import sys
import conn
import os
import extra_functions
import storage_volume

os.system('rm *.pyc')
if extra_functions.volume_check() == False:
  storage_volume.post()
result = extra_functions.volume_exist_check()
if len(result)>0:
  id = result[0]['id']
  
url = conn.url + 'storage/scrub/'
auth = conn.auth
headers = conn.headers
payload = {
          "scrub_volume": id,
          "scrub_dayweek": "7",
          "scrub_minute": "00",
          "scrub_hour": "00",
          "scrub_month": "*",
          "scrub_daymonth": "*"
}

def get():
  print 'Getting storage-scrub ......'
  r = requests.get(url, auth = auth)
  if r.status_code == 200:
    result = json.loads(r.text)
    i = 0
    for i in range(0,len(result)):
      print ''
      for items in result[i]:
        print items+':', result[i][items]
    print '\nGet storage-scrub --> Succeeded!'
  else:
    print 'Get storage-scrub --> Failed!'

def post():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  if len(result)>0:
    delete()
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 201:
    result = json.loads(r.text)
    print 'Create storage-scrub --> Succeeded!'
    return str(result['id'])+'/'
  else:
    print 'Create storage-scrub --> Failed!'
    return 'fail'

def put():
  id = post()
  r = requests.put(url+id, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 200:
    print 'Update storage-scrub --> Succeeded!'
  else:
    print 'Update storage-scrub --> Failed!'

def delete():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  if len(result)>0:
    for i in range(0,len(result)):
      r = requests.delete(url+str(result[i]['id'])+'/', auth = auth)
      if r.status_code == 204:
        print 'Delete storage-scrub --> Succeeded!'
      else:
        print 'Delete storage-scrub --> Failed!'
  else:
    id = post()
    r = requests.delete(url+id, auth = auth)
    if r.status_code == 204:
      print 'Delete storage-scrub --> Succeeded!'
    else:
      print 'Delete storage-scrub --> Failed!'
