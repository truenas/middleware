#!/usr/local/bin/python

import requests
import json
import sys
import conn
import os
import extra_functions

os.system('rm *.pyc')
headers = conn.headers
auth = conn.auth
payload = {
          "rsyncmod_name": "new_rsyncmod_test_suite",
          "rsyncmod_path": "/mnt/new_volume_test_suite"
}
url = conn.url + 'services/rsyncmod/'

if extra_functions.volume_check() == False:
  import storage_volume
  storage_volume.post()

def get():
  print 'Getting services-rsyncmod ......'
  r = requests.get(url, auth = auth)
  if r.status_code == 200:
    result = json.loads(r.text)
    i = 0
    for i in range(0,len(result)):
      print ''
      for items in result[i]:
        print items+':', result[i][items]
    print '\nGet services-rsyncmod --> Succeeded!'
  else:
    print 'Get services-rsyncmod --> Failed!'

def post():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  if len(result) > 0:
    delete()
  r = requests.post(url, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 201:
    result = json.loads(r.text)
    print 'Create services-rsyncmod --> Succeeded!'
    return str(result['id'])+'/'
  else:
    print 'Create services-rsyncmod --> Failed!'

def put():
  id = post()
  r = requests.put(url+id, auth = auth, data = json.dumps(payload), headers = headers)
  if r.status_code == 200:
    print 'Update services-rsyncmod --> Succeeded!'
  else:
    print 'Update services-rsyncmod --> Failed!'

def delete():
  r = requests.get(url, auth = auth)
  result = json.loads(r.text)
  i = 0
  for i in range(0,len(result)):
    r = requests.delete(url+str(result[i]['id'])+'/', auth = auth)
    if r.status_code == 204:
      print 'Delete services-rsyncmod --> Succeeded!'
    else:
      print 'Delete services-rsyncmod --> Failed!'
  if len(result) == 0:
    id = post()
    r = requests.delete(url+id, auth = auth)
    if r.status_code == 204:
      print 'Delete services-rsyncmod --> Succeeded!'
    else:
      print 'Delete services-rsyncmod --> Failed!'

